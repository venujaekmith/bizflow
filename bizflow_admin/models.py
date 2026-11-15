import uuid
from datetime import timedelta

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("Superusers must have staff and superuser permissions.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email


class Business(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROVISIONING = "provisioning", "Provisioning"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        DEACTIVATED = "deactivated", "Deactivated"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120, unique=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_businesses",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class BusinessMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Business Owner"
        ADMINISTRATOR = "administrator", "Administrator"
        MANAGER = "manager", "Manager"
        EMPLOYEE = "employee", "Employee"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="business_memberships"
    )
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="memberships"
    )
    custom_role = models.ForeignKey(
        "BusinessRole",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EMPLOYEE)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "business"], name="unique_business_membership"
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.business} ({self.role})"

    def can_manage_users(self):
        return self.role in {
            self.Role.OWNER,
            self.Role.ADMINISTRATOR,
        }


class BusinessInvitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="invitations"
    )
    email = models.EmailField()
    role = models.CharField(
        max_length=20,
        choices=BusinessMembership.Role.choices,
        default=BusinessMembership.Role.EMPLOYEE,
    )
    invited_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="sent_invitations"
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        return self.accepted_at is None and timezone.now() < self.expires_at


class BusinessSubscription(models.Model):
    class Status(models.TextChoices):
        TRIAL = "trial", "Trial"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past due"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    class Interval(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        ANNUAL = "annual", "Annual"

    business = models.OneToOneField(
        Business, on_delete=models.CASCADE, related_name="subscription"
    )
    plan = models.ForeignKey(
        "SubscriptionPlan",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subscriptions",
    )
    plan_name = models.CharField(max_length=100)
    interval = models.CharField(
        max_length=10, choices=Interval.choices, default=Interval.MONTHLY
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.TRIAL
    )
    started_at = models.DateTimeField(default=timezone.now)
    renews_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    provider = models.CharField(max_length=50, default="manual")
    external_subscription_id = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.business} - {self.plan_name}"


class SubscriptionPlan(models.Model):
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)
    annual_price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["monthly_price", "name"]

    def __str__(self):
        return f"{self.name} ({self.currency})"

    def price_for(self, interval):
        return self.annual_price if interval == "annual" else self.monthly_price


class PaymentRecord(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    business = models.ForeignKey(
        Business, on_delete=models.PROTECT, related_name="payments"
    )
    subscription = models.ForeignKey(
        BusinessSubscription,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    provider = models.CharField(max_length=50, default="manual")
    external_payment_id = models.CharField(max_length=200, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class BusinessApplication(models.Model):
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="applications"
    )
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=100)
    configuration = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "slug"], name="unique_business_application"
            )
        ]

    def __str__(self):
        return f"{self.business} - {self.name}"


class BusinessRole(models.Model):
    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="custom_roles"
    )
    name = models.CharField(max_length=100)
    permissions = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["business", "name"], name="unique_business_role"
            )
        ]

    def __str__(self):
        return f"{self.business} - {self.name}"


class BusinessSetting(models.Model):
    business = models.OneToOneField(
        Business, on_delete=models.CASCADE, related_name="settings"
    )
    display_name = models.CharField(max_length=200, blank=True)
    timezone = models.CharField(max_length=100, default="UTC")
    currency = models.CharField(max_length=3, default="USD")
    enabled_modules = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class AuditLog(models.Model):
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    business = models.ForeignKey(
        Business,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    action = models.CharField(max_length=100)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} at {self.created_at:%Y-%m-%d %H:%M:%S}"


class BusinessDatabase(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    business = models.OneToOneField(
        Business, on_delete=models.CASCADE, related_name="database"
    )
    engine = models.CharField(max_length=50, default="django.db.backends.postgresql")
    name = models.CharField(max_length=63, unique=True)
    host = models.CharField(max_length=255)
    port = models.PositiveIntegerField(default=5432)
    username = models.CharField(max_length=150)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.business} - {self.name}"


class ProvisioningAttempt(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    business = models.ForeignKey(
        Business, on_delete=models.CASCADE, related_name="provisioning_attempts"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.RUNNING
    )
    current_step = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=100, unique=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]


class ProvisioningStep(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    attempt = models.ForeignKey(
        ProvisioningAttempt, on_delete=models.CASCADE, related_name="steps"
    )
    name = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=Status.choices)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "name"], name="unique_provisioning_step"
            )
        ]
