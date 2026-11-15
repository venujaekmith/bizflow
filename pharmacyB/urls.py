from django.urls import path

from .views import dashboard

app_name = "pharmacyB"

urlpatterns = [
    path("", dashboard, name="dashboard"),
]
