from django.urls import path

from .platform_views import (
    business_create,
    business_list,
    dashboard,
    provision_business,
    subscription_overview,
    update_business_status,
)

app_name = "platform"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("businesses/", business_list, name="businesses"),
    path("businesses/create/", business_create, name="business_create"),
    path(
        "businesses/<uuid:business_id>/status/",
        update_business_status,
        name="business_status",
    ),
    path(
        "businesses/<uuid:business_id>/provision/",
        provision_business,
        name="business_provision",
    ),
    path("subscriptions/", subscription_overview, name="subscriptions"),
]
