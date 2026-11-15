from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    AuditLog,
    Business,
    BusinessApplication,
    BusinessInvitation,
    BusinessMembership,
    BusinessSubscription,
    PaymentRecord,
    SubscriptionPlan,
    BusinessDatabase,
    ProvisioningAttempt,
    ProvisioningStep,
    User,
)


@admin.register(User)
class PlatformUserAdmin(UserAdmin):
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "is_staff", "is_active")
    search_fields = ("email", "first_name", "last_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "status", "created_by", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "slug")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(BusinessMembership)
class BusinessMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "business", "role", "is_active", "joined_at")
    list_filter = ("role", "is_active")
    search_fields = ("user__email", "business__name")


@admin.register(BusinessInvitation)
class BusinessInvitationAdmin(admin.ModelAdmin):
    list_display = ("email", "business", "role", "expires_at", "accepted_at")
    list_filter = ("role",)
    search_fields = ("email", "business__name")
    readonly_fields = ("token", "created_at")


@admin.register(BusinessSubscription)
class BusinessSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "business",
        "plan_name",
        "interval",
        "status",
        "started_at",
        "renews_at",
    )
    list_filter = ("status", "plan_name")


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "monthly_price",
        "annual_price",
        "currency",
        "is_active",
    )
    list_filter = ("is_active", "currency")
    search_fields = ("name", "code")


@admin.register(PaymentRecord)
class PaymentRecordAdmin(admin.ModelAdmin):
    list_display = (
        "business",
        "amount",
        "currency",
        "status",
        "provider",
        "paid_at",
    )
    list_filter = ("status", "provider", "currency")
    search_fields = ("business__name", "external_payment_id")
    readonly_fields = ("created_at",)


@admin.register(BusinessApplication)
class BusinessApplicationAdmin(admin.ModelAdmin):
    list_display = ("name", "business", "slug", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug", "business__name")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "actor", "business", "created_at")
    list_filter = ("action",)
    search_fields = ("action", "actor__email", "business__name")
    readonly_fields = ("actor", "business", "action", "metadata", "created_at")


@admin.register(BusinessDatabase)
class BusinessDatabaseAdmin(admin.ModelAdmin):
    list_display = ("business", "name", "host", "port", "username", "status")
    list_filter = ("status",)
    search_fields = ("business__name", "name")
    readonly_fields = ("name", "created_at", "updated_at")


@admin.register(ProvisioningAttempt)
class ProvisioningAttemptAdmin(admin.ModelAdmin):
    list_display = ("business", "status", "current_step", "started_at", "completed_at")
    list_filter = ("status",)
    search_fields = ("business__name", "idempotency_key")
    readonly_fields = (
        "business",
        "status",
        "current_step",
        "error_message",
        "idempotency_key",
        "started_at",
        "completed_at",
    )


@admin.register(ProvisioningStep)
class ProvisioningStepAdmin(admin.ModelAdmin):
    list_display = ("attempt", "name", "status", "started_at", "completed_at")
    list_filter = ("status", "name")
    readonly_fields = (
        "attempt",
        "name",
        "status",
        "error_message",
        "started_at",
        "completed_at",
    )
