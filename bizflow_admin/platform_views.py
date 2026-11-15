from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.conf import settings
from django.db import connections
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import (
    AuditLog,
    Business,
    BusinessSubscription,
    ProvisioningAttempt,
    SubscriptionPlan,
)
from .platform_forms import PlatformBusinessForm
from .provisioning import BusinessProvisioner, ProvisioningError
from business_runtime.registry import get_application
from .models import BusinessApplication


staff_required = user_passes_test(lambda user: user.is_active and user.is_staff)


@staff_required
def dashboard(request):
    default_connection = connections["default"]
    context = {
        "business_count": Business.objects.count(),
        "active_business_count": Business.objects.filter(
            status=Business.Status.ACTIVE
        ).count(),
        "pending_business_count": Business.objects.filter(
            status__in=[Business.Status.PENDING, Business.Status.PROVISIONING]
        ).count(),
        "subscription_count": BusinessSubscription.objects.count(),
        "recent_businesses": Business.objects.select_related("created_by")[:10],
        "recent_attempts": ProvisioningAttempt.objects.select_related("business")[:10],
        "recent_activity": AuditLog.objects.select_related(
            "actor", "business"
        )[:10],
        "health": {
            "database_vendor": default_connection.vendor,
            "database_usable": default_connection.is_usable(),
            "debug": settings.DEBUG,
        },
    }
    return render(request, "platform/dashboard.html", context)


@staff_required
def business_list(request):
    businesses = Business.objects.select_related("created_by").prefetch_related(
        "subscription", "provisioning_attempts"
    )
    return render(
        request,
        "platform/businesses.html",
        {"businesses": businesses, "status_choices": Business.Status.choices},
    )


@staff_required
def business_create(request):
    form = PlatformBusinessForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        business = form.save(commit=False)
        business.created_by = request.user
        business.save()
        application = get_application(form.cleaned_data["application"])
        BusinessApplication.objects.create(
            business=business,
            name=application.key,
            slug=application.key.lower(),
        )
        AuditLog.objects.create(
            actor=request.user,
            business=business,
            action="business.created",
            metadata={"status": business.status},
        )
        messages.success(request, "Business created and ready for provisioning.")
        return redirect("platform:businesses")
    return render(
        request,
        "platform/business_form.html",
        {"form": form, "title": "Create business"},
    )


@staff_required
@require_POST
def update_business_status(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    status = request.POST.get("status")
    valid_statuses = {value for value, _ in Business.Status.choices}
    if status not in valid_statuses:
        messages.error(request, "Invalid business status.")
        return redirect("platform:businesses")
    business.status = status
    business.save(update_fields=["status", "updated_at"])
    AuditLog.objects.create(
        actor=request.user,
        business=business,
        action="business.status_changed",
        metadata={"status": status},
    )
    messages.success(request, "Business status updated.")
    return redirect("platform:businesses")


@staff_required
@require_POST
def provision_business(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    try:
        BusinessProvisioner().provision(business.id, business.created_by_id)
    except ProvisioningError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Business provisioning completed.")
    return redirect("platform:businesses")


@staff_required
def subscription_overview(request):
    subscriptions = BusinessSubscription.objects.select_related(
        "business", "plan"
    )
    plans = SubscriptionPlan.objects.filter(is_active=True)
    return render(
        request,
        "platform/subscriptions.html",
        {"subscriptions": subscriptions, "plans": plans},
    )
