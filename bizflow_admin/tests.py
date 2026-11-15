import tempfile
from pathlib import Path
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from unittest.mock import patch

from .models import (
    AuditLog,
    Business,
    BusinessApplication,
    BusinessDatabase,
    BusinessMembership,
    ProvisioningAttempt,
    ProvisioningStep,
    User,
    BusinessInvitation,
    BusinessSetting,
    BusinessSubscription,
    PaymentRecord,
    SubscriptionPlan,
)
from .provisioning import BusinessProvisioner, ProvisioningError


class AuthenticationTests(TestCase):
    def test_registration_creates_user_and_redirects_to_business_resolution(self):
        response = self.client.post(
            reverse("business:register"),
            {
                "email": "new@example.com",
                "first_name": "New",
                "last_name": "User",
                "password": "A-safe-password-123",
                "password_confirmation": "A-safe-password-123",
            },
        )

        self.assertRedirects(response, reverse("business:resolve"))
        self.assertTrue(User.objects.filter(email="new@example.com").exists())

    def test_inactive_user_cannot_log_in(self):
        User.objects.create_user(
            email="inactive@example.com",
            password="A-safe-password-123",
            is_active=False,
        )

        response = self.client.post(
            reverse("business:login"),
            {"username": "inactive@example.com", "password": "A-safe-password-123"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)


class BusinessAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com", password="A-safe-password-123"
        )
        self.other_user = User.objects.create_user(
            email="other@example.com", password="A-safe-password-123"
        )
        self.business = Business.objects.create(
            name="Green Leaf",
            slug="green-leaf-1024",
            status=Business.Status.ACTIVE,
            created_by=self.user,
        )

    def test_single_active_membership_redirects_to_business(self):
        BusinessMembership.objects.create(
            user=self.user,
            business=self.business,
            role=BusinessMembership.Role.OWNER,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("business:resolve"))

        self.assertRedirects(
            response,
            reverse("business:dashboard", kwargs={"slug": self.business.slug}),
        )

    def test_salon_business_uses_salon_dashboard_template(self):
        self.business.slug = "salonNEXT"
        self.business.save(update_fields=["slug", "updated_at"])
        BusinessMembership.objects.create(
            user=self.user,
            business=self.business,
            role=BusinessMembership.Role.OWNER,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("business:dashboard", kwargs={"slug": self.business.slug})
        )

        self.assertTemplateUsed(response, "salonNEXT/dashboard.html")

    def test_pharmacy_business_uses_pharmacy_dashboard_with_demo_data(self):
        self.business.slug = "pharmacyB"
        self.business.save(update_fields=["slug", "updated_at"])
        BusinessMembership.objects.create(
            user=self.user,
            business=self.business,
            role=BusinessMembership.Role.OWNER,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("business:dashboard", kwargs={"slug": self.business.slug})
        )

        self.assertTemplateUsed(response, "pharmacyB/dashboard.html")
        self.assertContains(response, "Paracetamol")

    def test_gracery_business_uses_gracery_dashboard_with_demo_data(self):
        self.business.slug = "graceryshopA"
        self.business.save(update_fields=["slug", "updated_at"])
        BusinessMembership.objects.create(
            user=self.user,
            business=self.business,
            role=BusinessMembership.Role.OWNER,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("business:dashboard", kwargs={"slug": self.business.slug})
        )

        self.assertTemplateUsed(response, "graceryshopA/dashboard.html")
        self.assertContains(response, "Rice")

    def test_user_cannot_open_another_business_dashboard(self):
        self.client.force_login(self.other_user)

        response = self.client.get(
            reverse("business:dashboard", kwargs={"slug": self.business.slug})
        )

        self.assertEqual(response.status_code, 403)

    def test_suspended_business_dashboard_is_denied_by_middleware(self):
        BusinessMembership.objects.create(
            user=self.user,
            business=self.business,
            role=BusinessMembership.Role.OWNER,
        )
        self.business.status = Business.Status.SUSPENDED
        self.business.save(update_fields=["status", "updated_at"])
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("business:dashboard", kwargs={"slug": self.business.slug})
        )

        self.assertEqual(response.status_code, 403)

    def test_multiple_business_selection_sets_active_business_session(self):
        second_business = Business.objects.create(
            name="Second Business",
            slug="second-business",
            status=Business.Status.ACTIVE,
            created_by=self.user,
        )
        first_membership = BusinessMembership.objects.create(
            user=self.user,
            business=self.business,
            role=BusinessMembership.Role.OWNER,
        )
        BusinessMembership.objects.create(
            user=self.user,
            business=second_business,
            role=BusinessMembership.Role.MANAGER,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("business:select"),
            {"membership_id": first_membership.id},
        )

        self.assertRedirects(
            response,
            reverse("business:dashboard", kwargs={"slug": self.business.slug}),
        )
        self.assertEqual(
            self.client.session["active_business_id"], str(self.business.id)
        )

    def test_suspended_business_is_not_resolved(self):
        BusinessMembership.objects.create(
            user=self.user,
            business=self.business,
            role=BusinessMembership.Role.OWNER,
        )
        self.business.status = Business.Status.SUSPENDED
        self.business.save(update_fields=["status", "updated_at"])
        self.client.force_login(self.user)

        response = self.client.get(reverse("business:resolve"))

        self.assertTemplateUsed(response, "business/no_access.html")


class ProvisioningTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="provision-owner@example.com",
            password="A-safe-password-123",
        )
        self.business = Business.objects.create(
            name="Provisioned Business",
            slug="provisioned-business",
            created_by=self.owner,
        )

    def test_sqlite_provisioning_creates_isolated_business_database(self):
        BusinessApplication.objects.create(
            business=self.business,
            name="salonNEXT",
            slug="salonnext",
        )
        with tempfile.TemporaryDirectory() as database_dir, override_settings(
            BUSINESS_DATABASE_DIR=database_dir
        ), patch.object(BusinessProvisioner, "_migrate_database"):
            BusinessProvisioner().provision(self.business.id)

            self.business.refresh_from_db()
            database = BusinessDatabase.objects.get(business=self.business)
            self.assertEqual(self.business.status, Business.Status.ACTIVE)
            self.assertEqual(database.status, BusinessDatabase.Status.PENDING)
            self.assertEqual(database.engine, "django.db.backends.sqlite3")
            self.assertTrue((Path(database_dir) / database.name).exists())

    def test_business_without_application_fails_explicitly(self):
        with self.assertRaises(ProvisioningError):
            BusinessProvisioner().provision(self.business.id)

        self.business.refresh_from_db()
        attempt = ProvisioningAttempt.objects.get(business=self.business)
        step = ProvisioningStep.objects.filter(attempt=attempt).order_by("id").last()
        self.assertEqual(self.business.status, Business.Status.FAILED)
        self.assertEqual(attempt.status, ProvisioningAttempt.Status.FAILED)
        self.assertEqual(step.status, ProvisioningStep.Status.FAILED)

    @patch.object(BusinessProvisioner, "_create_database")
    @patch.object(BusinessProvisioner, "_migrate_database")
    def test_successful_provisioning_is_idempotent(
        self, migrate_database, create_database
    ):
        provisioner = BusinessProvisioner()
        provisioner._create_initial_administrator = lambda business, owner_id: (
            BusinessMembership.objects.update_or_create(
                user_id=owner_id,
                business=business,
                defaults={"role": BusinessMembership.Role.OWNER, "is_active": True},
            )
        )
        first = provisioner.provision(self.business.id)
        second = provisioner.provision(self.business.id)

        self.assertEqual(first.id, second.id)
        self.business.refresh_from_db()
        self.assertEqual(self.business.status, Business.Status.ACTIVE)
        self.assertEqual(
            BusinessMembership.objects.filter(
                user=self.owner, business=self.business
            ).count(),
            1,
        )
        create_database.assert_called_once()
        migrate_database.assert_called_once()


class BusinessManagementTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="manager@example.com", password="A-safe-password-123"
        )
        self.business = Business.objects.create(
            name="Managed Business",
            slug="managed-business",
            status=Business.Status.ACTIVE,
            created_by=self.owner,
        )
        self.owner_membership = BusinessMembership.objects.create(
            user=self.owner,
            business=self.business,
            role=BusinessMembership.Role.OWNER,
        )
        self.client.force_login(self.owner)

    def test_owner_can_create_employee_and_activity_is_recorded(self):
        response = self.client.post(
            reverse(
                "business:employee_create", kwargs={"slug": self.business.slug}
            ),
            {
                "email": "employee@example.com",
                "first_name": "Employee",
                "last_name": "One",
                "password": "A-safe-password-123",
                "password_confirmation": "A-safe-password-123",
                "role": BusinessMembership.Role.EMPLOYEE,
            },
        )

        self.assertRedirects(
            response, reverse("business:employees", kwargs={"slug": self.business.slug})
        )
        employee = User.objects.get(email="employee@example.com")
        self.assertTrue(
            BusinessMembership.objects.filter(
                user=employee, business=self.business
            ).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                business=self.business, action="employee.created"
            ).exists()
        )

    def test_non_manager_cannot_manage_employees(self):
        employee = User.objects.create_user(
            email="regular@example.com", password="A-safe-password-123"
        )
        BusinessMembership.objects.create(
            user=employee,
            business=self.business,
            role=BusinessMembership.Role.EMPLOYEE,
        )
        self.client.force_login(employee)

        response = self.client.get(
            reverse("business:employees", kwargs={"slug": self.business.slug})
        )

        self.assertEqual(response.status_code, 403)

    def test_deactivation_is_limited_to_this_business(self):
        employee = User.objects.create_user(
            email="shared@example.com", password="A-safe-password-123"
        )
        employee_membership = BusinessMembership.objects.create(
            user=employee,
            business=self.business,
            role=BusinessMembership.Role.EMPLOYEE,
        )
        response = self.client.post(
            reverse(
                "business:employee_deactivate",
                kwargs={
                    "slug": self.business.slug,
                    "membership_id": employee_membership.id,
                },
            )
        )

        self.assertEqual(response.status_code, 302)
        employee.refresh_from_db()
        self.assertTrue(employee.is_active)

    def test_owner_can_invite_and_update_settings(self):
        invitation_response = self.client.post(
            reverse(
                "business:invite_employee", kwargs={"slug": self.business.slug}
            ),
            {"email": "invited@example.com", "role": BusinessMembership.Role.MANAGER},
        )
        settings_response = self.client.post(
            reverse("business:settings", kwargs={"slug": self.business.slug}),
            {
                "display_name": "Managed Business HQ",
                "timezone": "Asia/Colombo",
                "currency": "LKR",
                "enabled_modules": "reports, inventory",
            },
        )

        self.assertEqual(invitation_response.status_code, 302)
        self.assertEqual(settings_response.status_code, 302)
        self.assertTrue(
            BusinessInvitation.objects.filter(
                business=self.business, email="invited@example.com"
            ).exists()
        )
        business_settings = BusinessSetting.objects.get(business=self.business)
        self.assertEqual(business_settings.enabled_modules, ["reports", "inventory"])


class BillingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="billing-owner@example.com", password="A-safe-password-123"
        )
        self.business = Business.objects.create(
            name="Billing Business",
            slug="billing-business",
            status=Business.Status.ACTIVE,
            created_by=self.owner,
        )
        BusinessMembership.objects.create(
            user=self.owner,
            business=self.business,
            role=BusinessMembership.Role.OWNER,
        )
        self.plan = SubscriptionPlan.objects.create(
            code="starter",
            name="Starter",
            monthly_price="19.00",
            annual_price="190.00",
        )
        self.client.force_login(self.owner)

    def test_owner_can_select_plan_and_payment_is_pending(self):
        response = self.client.post(
            reverse("business:change_plan", kwargs={"slug": self.business.slug}),
            {"plan": self.plan.code, "interval": "monthly"},
        )

        self.assertRedirects(
            response, reverse("business:billing", kwargs={"slug": self.business.slug})
        )
        subscription = BusinessSubscription.objects.get(business=self.business)
        self.assertEqual(subscription.plan, self.plan)
        self.assertEqual(subscription.status, BusinessSubscription.Status.ACTIVE)
        self.assertTrue(
            PaymentRecord.objects.filter(
                business=self.business,
                status=PaymentRecord.Status.PENDING,
            ).exists()
        )

    def test_cancelled_subscription_blocks_business_access(self):
        BusinessSubscription.objects.create(
            business=self.business,
            plan=self.plan,
            plan_name=self.plan.name,
            status=BusinessSubscription.Status.CANCELLED,
        )

        response = self.client.get(
            reverse("business:dashboard", kwargs={"slug": self.business.slug})
        )

        self.assertEqual(response.status_code, 403)


class PlatformDashboardTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="platform@example.com",
            password="A-safe-password-123",
            is_staff=True,
        )
        self.user = User.objects.create_user(
            email="business@example.com", password="A-safe-password-123"
        )

    def test_staff_user_can_view_platform_dashboard(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("platform:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "platform/dashboard.html")

    def test_non_staff_user_cannot_view_platform_dashboard(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("platform:dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_staff_user_can_create_and_update_business(self):
        self.client.force_login(self.admin)
        create_response = self.client.post(
            reverse("platform:business_create"),
            {
                "name": "Platform Created",
                "slug": "platform-created",
                "status": Business.Status.PENDING,
                "application": "salonnext",
            },
        )
        business = Business.objects.get(slug="platform-created")
        status_response = self.client.post(
            reverse("platform:business_status", kwargs={"business_id": business.id}),
            {"status": Business.Status.ACTIVE},
        )

        self.assertRedirects(create_response, reverse("platform:businesses"))
        self.assertRedirects(status_response, reverse("platform:businesses"))
        business.refresh_from_db()
        self.assertEqual(business.created_by, self.admin)
        self.assertEqual(business.status, Business.Status.ACTIVE)
        self.assertTrue(business.applications.filter(slug="salonnext").exists())

    def test_provisioning_failure_is_visible_from_platform_action(self):
        business = Business.objects.create(
            name="Needs Provisioning",
            slug="needs-provisioning",
            status=Business.Status.PENDING,
            created_by=self.admin,
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("platform:business_provision", kwargs={"business_id": business.id})
        )

        self.assertRedirects(response, reverse("platform:businesses"))
        business.refresh_from_db()
        self.assertEqual(business.status, Business.Status.FAILED)
