from django.contrib import admin

from apps.orders.models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product", "product_name_snapshot", "quantity", "price_at_purchase"]
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["order_code", "customer", "status", "final_amount", "created_at"]
    list_filter = ["status", "payment_method"]
    search_fields = ["order_code", "customer__email"]
    list_select_related = ["customer"]
    inlines = [OrderItemInline]
    readonly_fields = ["order_code", "total_amount", "final_amount", "shipping_address_snapshot"]
