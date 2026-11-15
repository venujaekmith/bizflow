import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from bizflow_admin.models import Business, BusinessMembership
from business_runtime.database import business_database_context, business_database_alias

from .forms import AppointmentForm, CheckoutForm, CustomerForm, ServiceForm
from .models import Appointment, Customer, Sale, SaleItem, Service


def _business(request, business_slug):
    business = get_object_or_404(
        Business, slug=business_slug, status=Business.Status.ACTIVE
    )
    get_object_or_404(
        BusinessMembership,
        business=business,
        user=request.user,
        is_active=True,
    )
    return business


def _database_ready(business):
    database = getattr(business, "database", None)
    return bool(database and database.status == "ready")


def _not_ready_response():
    return HttpResponse(
        "Salon data operations require the isolated business database to be ready.",
        status=503,
    )


@login_required
def dashboard(request, business_slug=None):
    business_slug = business_slug or request.resolver_match.kwargs.get("business_slug")
    business = _business(request, business_slug)
    membership = BusinessMembership.objects.get(
        business=business, user=request.user, is_active=True
    )
    context = {
        "business": business,
        "membership": membership,
        "customer_count": 24,
        "appointment_count": 8,
        "service_count": 6,
        "today_revenue": "1250.00",
        "recent_appointments": [],
        "demo_mode": True,
    }
    if _database_ready(business):
        with business_database_context(business):
            today = timezone.localdate()
            context.update(
                customer_count=Customer.objects.count(),
                appointment_count=Appointment.objects.count(),
                service_count=Service.objects.filter(is_active=True).count(),
                today_revenue=sum(
                    sale.total
                    for sale in Sale.objects.filter(sold_at__date=today)
                ),
                recent_appointments=list(
                    Appointment.objects.select_related("customer", "service")[:8]
                ),
                demo_mode=False,
            )
    return render(request, "salonNEXT/dashboard.html", context)


@login_required
def customer_list(request, business_slug):
    business = _business(request, business_slug)
    if not _database_ready(business):
        return _not_ready_response()
    with business_database_context(business):
        customers = list(Customer.objects.all())
    return render(
        request,
        "salonNEXT/customers.html",
        {"business": business, "customers": customers},
    )


@login_required
def customer_create(request, business_slug):
    business = _business(request, business_slug)
    if not _database_ready(business):
        return _not_ready_response()
    with business_database_context(business):
        form = CustomerForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            form.save()
            messages.success(request, "Customer saved.")
            return redirect("salonNEXT:customers", business_slug=business_slug)
    return render(
        request,
        "salonNEXT/form.html",
        {"business": business, "form": form, "title": "Add customer"},
    )


@login_required
def service_list(request, business_slug):
    business = _business(request, business_slug)
    if not _database_ready(business):
        return _not_ready_response()
    with business_database_context(business):
        services = list(Service.objects.all())
    return render(
        request,
        "salonNEXT/services.html",
        {"business": business, "services": services},
    )


@login_required
def service_create(request, business_slug):
    business = _business(request, business_slug)
    if not _database_ready(business):
        return _not_ready_response()
    with business_database_context(business):
        form = ServiceForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            form.save()
            messages.success(request, "Service saved.")
            return redirect("salonNEXT:services", business_slug=business_slug)
    return render(
        request,
        "salonNEXT/form.html",
        {"business": business, "form": form, "title": "Add service"},
    )


@login_required
def appointment_list(request, business_slug):
    business = _business(request, business_slug)
    if not _database_ready(business):
        return _not_ready_response()
    with business_database_context(business):
        appointments = list(
            Appointment.objects.select_related("customer", "service")
        )
    return render(
        request,
        "salonNEXT/appointments.html",
        {"business": business, "appointments": appointments},
    )


@login_required
def appointment_create(request, business_slug):
    business = _business(request, business_slug)
    if not _database_ready(business):
        return _not_ready_response()
    with business_database_context(business):
        form = AppointmentForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            form.save()
            messages.success(request, "Appointment booked.")
            return redirect("salonNEXT:appointments", business_slug=business_slug)
    return render(
        request,
        "salonNEXT/form.html",
        {"business": business, "form": form, "title": "Book appointment"},
    )


@login_required
def point_of_sale(request, business_slug):
    business = _business(request, business_slug)
    if not _database_ready(business):
        return _not_ready_response()
    alias = business_database_alias(business.id)
    with business_database_context(business):
        form = CheckoutForm(request.POST or None)
        form.fields["customer"].queryset = Customer.objects.using(alias).all()
        form.fields["service"].queryset = Service.objects.using(alias).filter(
            is_active=True
        )
        if request.method == "POST" and form.is_valid():
            service = form.cleaned_data["service"]
            quantity = form.cleaned_data["quantity"]
            subtotal = service.price * quantity
            discount = form.cleaned_data["discount"]
            total = subtotal - discount
            with transaction.atomic():
                sale = Sale.objects.create(
                    receipt_number=f"SN-{uuid.uuid4().hex[:10].upper()}",
                    customer=form.cleaned_data["customer"],
                    subtotal=subtotal,
                    discount=discount,
                    total=total,
                    payment_method=form.cleaned_data["payment_method"],
                )
                SaleItem.objects.create(
                    sale=sale,
                    service=service,
                    quantity=quantity,
                    unit_price=service.price,
                )
            messages.success(request, f"Sale completed: {sale.receipt_number}.")
            return redirect("salonNEXT:pos", business_slug=business_slug)
    return render(
        request,
        "salonNEXT/pos.html",
        {"business": business, "form": form},
    )


@login_required
def sales_list(request, business_slug):
    business = _business(request, business_slug)
    if not _database_ready(business):
        return _not_ready_response()
    with business_database_context(business):
        sales = list(Sale.objects.select_related("customer")[:100])
    return render(
        request,
        "salonNEXT/sales.html",
        {"business": business, "sales": sales},
    )
