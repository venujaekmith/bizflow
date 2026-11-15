from django.contrib import admin

from .models import Appointment, Customer, Sale, SaleItem, Service


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email", "created_at")
    search_fields = ("name", "phone", "email")


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "duration_minutes", "price", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("customer", "service_name", "starts_at", "status")
    list_filter = ("status", "starts_at")
    search_fields = ("customer__name", "service_name")


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "customer", "total", "payment_method", "sold_at")
    list_filter = ("payment_method", "sold_at")
    search_fields = ("receipt_number", "customer__name")


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ("sale", "service", "quantity", "unit_price")
