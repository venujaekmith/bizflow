from django.contrib import admin

from .models import Product, Sale


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "price", "stock_quantity", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "sku")


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("product", "quantity", "total", "sold_at")
    search_fields = ("product__name",)
