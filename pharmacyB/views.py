from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from bizflow_admin.models import Business, BusinessMembership
from business_runtime.database import business_database_context

from .models import Medicine, Prescription


def dashboard(request, business_slug=None):
    business = get_object_or_404(
        Business, slug=business_slug, status=Business.Status.ACTIVE
    )
    membership = get_object_or_404(
        BusinessMembership, business=business, user=request.user, is_active=True
    )
    medicine_names = ["Paracetamol", "Amoxicillin", "Vitamin C"]
    prescriptions_today = 12
    database = getattr(business, "database", None)
    if database and database.status == "ready":
        with business_database_context(business):
            medicine_names = list(
                Medicine.objects.values_list("name", flat=True)
            )
            prescriptions_today = Prescription.objects.filter(
                prescribed_at__date=timezone.now().date()
            ).count()
    return render(
        request,
        "pharmacyB/dashboard.html",
        {
            "business": business,
            "membership": membership,
            "medicine_names": medicine_names,
            "prescriptions_today": prescriptions_today,
        },
    )
