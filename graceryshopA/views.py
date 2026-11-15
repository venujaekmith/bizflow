from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from bizflow_admin.models import Business, BusinessMembership
from business_runtime.database import business_database_context

from .models import Product, Sale


def dashboard(request, business_slug=None):
    business = get_object_or_404(
        Business, slug=business_slug, status=Business.Status.ACTIVE
    )
    membership = get_object_or_404(
        BusinessMembership, business=business, user=request.user, is_active=True
    )
    products = ["Rice", "Milk", "Bread"]
    sales_today = 18
    database = getattr(business, "database", None)
    if database and database.status == "ready":
        with business_database_context(business):
            products = list(Product.objects.filter(is_active=True).values_list("name", flat=True))
            sales_today = Sale.objects.filter(sold_at__date=timezone.now().date()).count()
    return render(
        request,
        "graceryshopA/dashboard.html",
        {
            "business": business,
            "membership": membership,
            "product_names": products,
            "sales_today": sales_today,
        },
    )
