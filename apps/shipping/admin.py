from django.contrib import admin

from apps.shipping.models import Shipping


@admin.register(Shipping)
class ShippingAdmin(admin.ModelAdmin):
    list_display = ["tracking_code", "order", "status", "shipping_fee", "delivered_at"]
    list_filter = ["status"]
    list_select_related = ["order"]
    search_fields = ["tracking_code", "order__order_code"]
    readonly_fields = ["order", "tracking_code"]
