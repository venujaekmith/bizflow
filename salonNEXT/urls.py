from django.urls import path

from .views import (
    appointment_create,
    appointment_list,
    customer_create,
    customer_list,
    dashboard,
    point_of_sale,
    sales_list,
    service_create,
    service_list,
)

app_name = "salonNEXT"

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("customers/", customer_list, name="customers"),
    path("customers/add/", customer_create, name="customer_create"),
    path("services/", service_list, name="services"),
    path("services/add/", service_create, name="service_create"),
    path("appointments/", appointment_list, name="appointments"),
    path("appointments/book/", appointment_create, name="appointment_create"),
    path("pos/", point_of_sale, name="pos"),
    path("sales/", sales_list, name="sales"),
]
