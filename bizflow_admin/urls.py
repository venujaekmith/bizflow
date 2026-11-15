from django.contrib.auth import views as auth_views
from django.urls import include, path

from .views import (
    PlatformLoginView,
    business_dashboard,
    accept_invitation,
    activity_log,
    business_settings,
    billing,
    cancel_subscription,
    change_plan,
    employee_create,
    employee_deactivate,
    employee_list,
    employee_role,
    invite_employee,
    register,
    resolve_business,
    select_business,
)

app_name = "business"

urlpatterns = [
    path("login/", PlatformLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("register/", register, name="register"),
    path("business/", resolve_business, name="resolve"),
    path("business/select/", select_business, name="select"),
    path("business/<slug:slug>/", business_dashboard, name="dashboard"),
    path(
        "business/<slug:business_slug>/salon/",
        include(("salonNEXT.urls", "salonNEXT")),
    ),
    path("business/<slug:slug>/employees/", employee_list, name="employees"),
    path(
        "business/<slug:slug>/employees/add/",
        employee_create,
        name="employee_create",
    ),
    path(
        "business/<slug:slug>/employees/<uuid:membership_id>/deactivate/",
        employee_deactivate,
        name="employee_deactivate",
    ),
    path(
        "business/<slug:slug>/employees/<uuid:membership_id>/role/",
        employee_role,
        name="employee_role",
    ),
    path(
        "business/<slug:slug>/employees/invite/",
        invite_employee,
        name="invite_employee",
    ),
    path("business/<slug:slug>/settings/", business_settings, name="settings"),
    path("business/<slug:slug>/activity/", activity_log, name="activity"),
    path("business/<slug:slug>/billing/", billing, name="billing"),
    path(
        "business/<slug:slug>/billing/change-plan/",
        change_plan,
        name="change_plan",
    ),
    path(
        "business/<slug:slug>/billing/cancel/",
        cancel_subscription,
        name="cancel_subscription",
    ),
    path(
        "business/invitations/<uuid:token>/accept/",
        accept_invitation,
        name="accept_invitation",
    ),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html"
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]
