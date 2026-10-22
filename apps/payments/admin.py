from django.contrib import admin

from apps.payments.models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["order", "amount", "method", "status", "paid_at"]
    list_filter = ["method", "status"]
    list_select_related = ["order"]
    search_fields = ["order__order_code", "transaction_id"]
    readonly_fields = ["order", "amount"]  # chỉ status/transaction_id đổi qua service, nhưng cho sửa tay khi cần fix data
