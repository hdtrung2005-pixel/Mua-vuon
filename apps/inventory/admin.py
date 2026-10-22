from django.contrib import admin

from apps.inventory.models import Inventory, InventoryTransaction


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ["product", "quantity", "low_stock_threshold", "is_low_stock", "is_out_of_stock"]
    list_select_related = ["product"]
    search_fields = ["product__name", "product__sku"]
    # quantity chỉ đổi qua services (reserve/receive/adjust), không cho sửa tay ở đây
    # để luôn có InventoryTransaction ghi log — tránh lệch lịch sử kho.
    readonly_fields = ["quantity"]


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = ["inventory", "transaction_type", "quantity", "reference_type", "created_by", "created_at"]
    list_filter = ["transaction_type", "reference_type"]
    list_select_related = ["inventory__product", "created_by"]
    readonly_fields = [f.name for f in InventoryTransaction._meta.fields]  # immutable log

    def has_add_permission(self, request):
        return False  # chỉ tạo qua services, không tạo tay trong Admin

    def has_delete_permission(self, request, obj=None):
        return False
