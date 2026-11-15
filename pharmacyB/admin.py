from django.contrib import admin

from .models import Medicine, Prescription


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ("name", "batch_number", "expiry_date", "stock_quantity")
    search_fields = ("name", "batch_number")


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ("patient_name", "medicine", "quantity", "prescribed_at")
    search_fields = ("patient_name", "medicine__name")
