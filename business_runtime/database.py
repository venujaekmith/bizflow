from contextlib import contextmanager
from contextvars import ContextVar

from django.conf import settings
from django.db import connections
from pathlib import Path

_current_business_id = ContextVar("current_business_id", default=None)


def business_database_alias(business_id):
    return f"business_{business_id.hex}"


@contextmanager
def business_database_context(business):
    configure_business_database(business)
    token = _current_business_id.set(business.id)
    try:
        yield business_database_alias(business.id)
    finally:
        _current_business_id.reset(token)


def current_business_database_alias():
    business_id = _current_business_id.get()
    return business_database_alias(business_id) if business_id else None


def configure_business_database(business):
    database = getattr(business, "database", None)
    if database is None:
        return None
    alias = business_database_alias(business.id)
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
    return alias


class BusinessDatabaseRouter:
    def db_for_read(self, model, **hints):
        return current_business_database_alias() if _is_business_model(model) else None

    def db_for_write(self, model, **hints):
        return current_business_database_alias() if _is_business_model(model) else None

    def allow_relation(self, obj1, obj2, **hints):
        if _is_business_model(obj1) or _is_business_model(obj2):
            return _database_for_object(obj1) == _database_for_object(obj2)
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in _business_app_labels():
            return db.startswith("business_")
        return not db.startswith("business_")


def _is_business_model(model_or_object):
    app_label = getattr(getattr(model_or_object, "_meta", None), "app_label", "")
    return app_label in _business_app_labels()


def _database_for_object(obj):
    business_id = getattr(obj, "business_id", None)
    return business_database_alias(business_id) if business_id else None


def _business_app_labels():
    from .registry import all_applications

    return {application.migration_label for application in all_applications()}
