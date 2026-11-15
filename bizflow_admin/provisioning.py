import re
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.db import connections, transaction
from django.utils import timezone

from .models import (
    Business,
    BusinessDatabase,
    BusinessMembership,
    ProvisioningAttempt,
    ProvisioningStep,
    User,
)
from business_runtime.registry import application_for_business


class ProvisioningError(RuntimeError):
    pass


class BusinessProvisioner:
    def provision(self, business_id, owner_user_id=None):
        with transaction.atomic():
            business = Business.objects.select_for_update().get(pk=business_id)
            owner_id = owner_user_id or business.created_by_id
            attempt_key = f"{business.id}:{owner_id}"
            attempt, _ = ProvisioningAttempt.objects.get_or_create(
                idempotency_key=attempt_key,
                defaults={"business": business},
            )
            if attempt.status == ProvisioningAttempt.Status.SUCCEEDED:
                return business
            attempt.status = ProvisioningAttempt.Status.RUNNING
            attempt.error_message = ""
            attempt.completed_at = None
            attempt.save(update_fields=["status", "error_message", "completed_at"])
            business.status = Business.Status.PROVISIONING
            business.save(update_fields=["status", "updated_at"])

        try:
            self._run_step(attempt, "create_database", self._create_database, business)
            self._run_step(attempt, "migrate_database", self._migrate_database, business)
            self._run_step(
                attempt,
                "create_initial_administrator",
                self._create_initial_administrator,
                business,
                owner_id,
            )
            with transaction.atomic():
                business.status = Business.Status.ACTIVE
                business.save(update_fields=["status", "updated_at"])
                attempt.status = ProvisioningAttempt.Status.SUCCEEDED
                attempt.current_step = ""
                attempt.completed_at = timezone.now()
                attempt.save(
                    update_fields=[
                        "status",
                        "current_step",
                        "completed_at",
                    ]
                )
            return business
        except Exception as exc:
            with transaction.atomic():
                business.status = Business.Status.FAILED
                business.save(update_fields=["status", "updated_at"])
                attempt.status = ProvisioningAttempt.Status.FAILED
                attempt.error_message = str(exc)
                attempt.completed_at = timezone.now()
                attempt.save(
                    update_fields=["status", "error_message", "completed_at"]
                )
            if isinstance(exc, ProvisioningError):
                raise
            raise ProvisioningError("Business provisioning failed.") from exc

    def _run_step(self, attempt, name, operation, *args):
        step, _ = ProvisioningStep.objects.get_or_create(
            attempt=attempt,
            name=name,
            defaults={"status": ProvisioningStep.Status.RUNNING},
        )
        step.status = ProvisioningStep.Status.RUNNING
        step.error_message = ""
        step.completed_at = None
        step.save(update_fields=["status", "error_message", "completed_at"])
        attempt.current_step = name
        attempt.save(update_fields=["current_step"])
        try:
            result = operation(*args)
        except Exception as exc:
            step.status = ProvisioningStep.Status.FAILED
            step.error_message = str(exc)
            step.completed_at = timezone.now()
            step.save(update_fields=["status", "error_message", "completed_at"])
            raise
        step.status = ProvisioningStep.Status.SUCCEEDED
        step.completed_at = timezone.now()
        step.save(update_fields=["status", "completed_at"])
        return result

    def _create_database(self, business):
        default_connection = connections["default"]
        if default_connection.vendor == "sqlite":
            database_name = f"bizflow_business_{business.id.hex}.sqlite3"
            database_dir = Path(
                getattr(settings, "BUSINESS_DATABASE_DIR", settings.BASE_DIR)
            )
            database_dir.mkdir(parents=True, exist_ok=True)
            database_path = database_dir / database_name
            database_path.touch(exist_ok=True)
            BusinessDatabase.objects.update_or_create(
                business=business,
                defaults={
                    "engine": "django.db.backends.sqlite3",
                    "name": database_name,
                    "host": "",
                    "port": 0,
                    "username": "",
                    "status": BusinessDatabase.Status.PENDING,
                },
            )
            return
        if default_connection.vendor != "postgresql":
            raise ProvisioningError(
                "Business database provisioning supports SQLite and PostgreSQL only."
            )

        database_name = f"bizflow_business_{business.id.hex}"
        if not re.fullmatch(r"[a-z0-9_]{1,63}", database_name):
            raise ProvisioningError("Generated database name is invalid.")

        with default_connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", [database_name]
            )
            if cursor.fetchone() is None:
                cursor.execute(
                    f"CREATE DATABASE {default_connection.ops.quote_name(database_name)}"
                )

        config = default_connection.settings_dict
        BusinessDatabase.objects.update_or_create(
            business=business,
            defaults={
                "engine": "django.db.backends.postgresql",
                "name": database_name,
                "host": config.get("HOST", ""),
                "port": int(config.get("PORT") or 5432),
                "username": config.get("USER", ""),
                "status": BusinessDatabase.Status.PENDING,
            },
        )

    def _migrate_database(self, business):
        database = business.database
        alias = f"business_{business.id.hex}"
        source = connections["default"].settings_dict.copy()
        if database.engine == "django.db.backends.sqlite3":
            database_dir = Path(
                getattr(settings, "BUSINESS_DATABASE_DIR", settings.BASE_DIR)
            )
            source.update(
                {
                    "ENGINE": database.engine,
                    "NAME": str(database_dir / database.name),
                    "OPTIONS": {},
                }
            )
        else:
            source.update(
                {
                    "ENGINE": database.engine,
                    "NAME": database.name,
                    "HOST": database.host,
                    "PORT": database.port,
                    "USER": database.username,
                }
            )
        connections.databases[alias] = source
        try:
            application = application_for_business(business)
            if application is None:
                raise ProvisioningError(
                    "Business has no registered application configured."
                )
            app_labels = [application.migration_label]
            for app_label in app_labels:
                call_command(
                    "migrate",
                    app_label,
                    database=alias,
                    interactive=False,
                    verbosity=0,
                )
        finally:
            connections[alias].close()
            connections.databases.pop(alias, None)
        database.status = BusinessDatabase.Status.READY
        database.save(update_fields=["status", "updated_at"])

    def _create_initial_administrator(self, business, owner_user_id):
        owner = User.objects.get(pk=owner_user_id)
        BusinessMembership.objects.update_or_create(
            user=owner,
            business=business,
            defaults={
                "role": BusinessMembership.Role.OWNER,
                "is_active": True,
            },
        )
