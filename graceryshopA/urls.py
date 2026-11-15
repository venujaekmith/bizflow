from django.urls import path

from .views import dashboard

app_name = "graceryshopA"

urlpatterns = [
    path("", dashboard, name="dashboard"),
]
