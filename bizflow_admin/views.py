from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.mail import send_mail
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    BusinessSettingForm,
    EmployeeForm,
    EmployeeRoleForm,
    InvitationForm,
    RegistrationForm,
)
from .billing import BillingService
from .models import (
    AuditLog,
    Business,
    BusinessInvitation,
    BusinessMembership,
    BusinessSetting,
    BusinessSubscription,
    PaymentRecord,
    SubscriptionPlan,
)
from business_runtime.registry import application_for_business


BUSINESS_DASHBOARD_TEMPLATES = {
    "graceryshopa": "graceryshopA/dashboard.html",
    "pharmacyb": "pharmacyB/dashboard.html",
    "salonnext": "salonNEXT/dashboard.html",
}


class PlatformLoginView(LoginView):
    template_name = "registration/login.html"


def _business_membership(request, slug, management=False):
    membership = (
        BusinessMembership.objects.select_related("business")
        .filter(
            user=request.user,
            is_active=True,
            business__slug=slug,
            business__status=Business.Status.ACTIVE,
        )
        .first()
    )
    if membership is None:
        return None
    if management and not membership.can_manage_users():
        return None
    return membership


def _record_activity(actor, business, action, metadata=None):
    AuditLog.objects.create(
        actor=actor,
        business=business,
        action=action,
        metadata=metadata or {},
    )


def register(request):
    if request.user.is_authenticated:
        return redirect("business:resolve")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("business:resolve")
    return render(request, "registration/register.html", {"form": form})


@login_required
def resolve_business(request):
    memberships = (
        BusinessMembership.objects.select_related("business")
        .filter(user=request.user, is_active=True, business__status=Business.Status.ACTIVE)
    )
    if memberships.count() == 0:
        return render(request, "business/no_access.html")
    if memberships.count() == 1:
        return redirect(
            "business:dashboard", slug=memberships.first().business.slug
        )
    return render(request, "business/select.html", {"memberships": memberships})


@login_required
@require_POST
def select_business(request):
    membership = (
        BusinessMembership.objects.select_related("business")
        .filter(
            id=request.POST.get("membership_id"),
            user=request.user,
            is_active=True,
            business__status=Business.Status.ACTIVE,
        )
        .first()
    )
    if membership is None:
        return HttpResponseForbidden("You do not have access to that business.")
    request.session["active_business_id"] = str(membership.business_id)
    return redirect("business:dashboard", slug=membership.business.slug)


@login_required
def business_dashboard(request, slug):
    membership = _business_membership(request, slug)
    if membership is None:
        return HttpResponseForbidden("You do not have access to this business.")
    request.session["active_business_id"] = str(membership.business_id)
    application = application_for_business(membership.business)
    if application:
        from django.utils.module_loading import import_string

        dashboard = import_string(f"{application.package}.views.dashboard")
        return dashboard(request, business_slug=slug)
    template_name = (
        application.dashboard_template
        if application
        else BUSINESS_DASHBOARD_TEMPLATES.get(
            membership.business.slug.lower(),
            "business/dashboard.html",
        )
    )
    return render(
        request,
        template_name,
        {"business": membership.business, "membership": membership},
    )


@login_required
def employee_list(request, slug):
    membership = _business_membership(request, slug, management=True)
    if membership is None:
        return HttpResponseForbidden("You do not have permission to manage employees.")
    employees = (
        BusinessMembership.objects.select_related("user", "custom_role")
        .filter(business=membership.business)
        .order_by("user__email")
    )
    return render(
        request,
        "business/employees/list.html",
        {
            "business": membership.business,
            "membership": membership,
            "employees": employees,
            "role_choices": [
                choice
                for choice in BusinessMembership.Role.choices
                if choice[0] != BusinessMembership.Role.OWNER
            ],
        },
    )


@login_required
def employee_create(request, slug):
    membership = _business_membership(request, slug, management=True)
    if membership is None:
        return HttpResponseForbidden("You do not have permission to manage employees.")
    form = EmployeeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save_user()
            BusinessMembership.objects.create(
                user=user,
                business=membership.business,
                role=form.cleaned_data["role"],
            )
            _record_activity(
                request.user,
                membership.business,
                "employee.created",
                {"user_id": str(user.id), "email": user.email},
            )
        messages.success(request, "Employee account created.")
        return redirect("business:employees", slug=slug)
    return render(
        request,
        "business/employees/form.html",
        {"business": membership.business, "form": form, "title": "Add employee"},
    )


@login_required
@require_POST
def employee_deactivate(request, slug, membership_id):
    membership = _business_membership(request, slug, management=True)
    if membership is None:
        return HttpResponseForbidden("You do not have permission to manage employees.")
    employee_membership = get_object_or_404(
        BusinessMembership, id=membership_id, business=membership.business
    )
    if employee_membership.role == BusinessMembership.Role.OWNER:
        return HttpResponseForbidden("The business owner cannot be deactivated here.")
    employee_membership.is_active = False
    employee_membership.save(update_fields=["is_active"])
    _record_activity(
        request.user,
        membership.business,
        "employee.deactivated",
        {"user_id": str(employee_membership.user_id)},
    )
    messages.success(request, "Employee access deactivated.")
    return redirect("business:employees", slug=slug)


@login_required
@require_POST
def employee_role(request, slug, membership_id):
    membership = _business_membership(request, slug, management=True)
    if membership is None:
        return HttpResponseForbidden("You do not have permission to manage employees.")
    employee_membership = get_object_or_404(
        BusinessMembership, id=membership_id, business=membership.business
    )
    if employee_membership.role == BusinessMembership.Role.OWNER:
        return HttpResponseForbidden("The business owner role cannot be changed here.")
    form = EmployeeRoleForm(request.POST, instance=employee_membership)
    form.fields["role"].choices = [
        choice
        for choice in BusinessMembership.Role.choices
        if choice[0] != BusinessMembership.Role.OWNER
    ]
    if form.is_valid():
        form.save()
        _record_activity(
            request.user,
            membership.business,
            "employee.role_changed",
            {"user_id": str(employee_membership.user_id), "role": employee_membership.role},
        )
    else:
        messages.error(request, "The selected employee role is invalid.")
    return redirect("business:employees", slug=slug)


@login_required
def invite_employee(request, slug):
    membership = _business_membership(request, slug, management=True)
    if membership is None:
        return HttpResponseForbidden("You do not have permission to manage employees.")
    form = InvitationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        invitation = form.save(commit=False)
        invitation.business = membership.business
        invitation.invited_by = request.user
        invitation.save()
        invitation_url = request.build_absolute_uri(
            reverse("business:accept_invitation", kwargs={"token": invitation.token})
        )
        send_mail(
            f"Invitation to join {membership.business.name}",
            f"Use this invitation link to join BizFlow: {invitation_url}",
            None,
            [invitation.email],
        )
        _record_activity(
            request.user,
            membership.business,
            "employee.invited",
            {"email": invitation.email, "role": invitation.role},
        )
        messages.success(request, "Invitation created and sent.")
        return redirect("business:employees", slug=slug)
    return render(
        request,
        "business/employees/form.html",
        {"business": membership.business, "form": form, "title": "Invite employee"},
    )


@login_required
def business_settings(request, slug):
    membership = _business_membership(request, slug, management=True)
    if membership is None:
        return HttpResponseForbidden("You do not have permission to manage settings.")
    settings, _ = BusinessSetting.objects.get_or_create(business=membership.business)
    form = BusinessSettingForm(request.POST or None, instance=settings)
    if request.method == "POST" and form.is_valid():
        form.save()
        _record_activity(request.user, membership.business, "business.settings_updated")
        messages.success(request, "Business settings updated.")
        return redirect("business:settings", slug=slug)
    return render(
        request,
        "business/settings.html",
        {"business": membership.business, "form": form},
    )


@login_required
def activity_log(request, slug):
    membership = _business_membership(request, slug, management=True)
    if membership is None:
        return HttpResponseForbidden("You do not have permission to view activity.")
    activities = AuditLog.objects.select_related("actor").filter(
        business=membership.business
    )[:100]
    return render(
        request,
        "business/activity.html",
        {"business": membership.business, "activities": activities},
    )


@login_required
def billing(request, slug):
    membership = _business_membership(request, slug, management=True)
    if membership is None:
        return HttpResponseForbidden("You do not have permission to manage billing.")
    subscription = getattr(membership.business, "subscription", None)
    plans = SubscriptionPlan.objects.filter(is_active=True)
    payments = PaymentRecord.objects.filter(business=membership.business)[:20]
    return render(
        request,
        "business/billing.html",
        {
            "business": membership.business,
            "subscription": subscription,
            "plans": plans,
            "payments": payments,
        },
    )


@login_required
@require_POST
def change_plan(request, slug):
    membership = _business_membership(request, slug, management=True)
    if membership is None:
        return HttpResponseForbidden("You do not have permission to manage billing.")
    plan = get_object_or_404(
        SubscriptionPlan,
        code=request.POST.get("plan"),
        is_active=True,
    )
    interval = request.POST.get("interval", BusinessSubscription.Interval.MONTHLY)
    try:
        subscription = BillingService().change_plan(
            membership.business, plan, interval
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("business:billing", slug=slug)
    BillingService().record_payment(
        subscription,
        plan.price_for(interval),
        PaymentRecord.Status.PENDING,
    )
    _record_activity(
        request.user,
        membership.business,
        "subscription.plan_changed",
        {"plan": plan.code, "interval": interval},
    )
    messages.success(request, "Subscription plan updated.")
    return redirect("business:billing", slug=slug)


@login_required
@require_POST
def cancel_subscription(request, slug):
    membership = _business_membership(request, slug, management=True)
    if membership is None:
        return HttpResponseForbidden("You do not have permission to manage billing.")
    if not getattr(membership.business, "subscription", None):
        messages.error(request, "This business has no subscription.")
        return redirect("business:billing", slug=slug)
    BillingService().cancel(membership.business)
    _record_activity(request.user, membership.business, "subscription.cancelled")
    messages.success(request, "Subscription cancelled.")
    return redirect("business:billing", slug=slug)


@login_required
def accept_invitation(request, token):
    invitation = get_object_or_404(
        BusinessInvitation.objects.select_related("business"),
        token=token,
    )
    if not invitation.is_valid or invitation.email.lower() != request.user.email.lower():
        return HttpResponseForbidden("This invitation is invalid or expired.")
    BusinessMembership.objects.update_or_create(
        user=request.user,
        business=invitation.business,
        defaults={"role": invitation.role, "is_active": True},
    )
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["accepted_at"])
    _record_activity(request.user, invitation.business, "employee.invitation_accepted")
    return redirect("business:dashboard", slug=invitation.business.slug)
