from django.contrib import admin

from apps.refunds.models import RefundRequest


@admin.register(RefundRequest)
class RefundRequestAdmin(admin.ModelAdmin):
    list_display = ["order", "amount", "status", "processed_by", "processed_at"]
    list_filter = ["status"]
    list_select_related = ["order", "processed_by"]
    search_fields = ["order__order_code"]
    readonly_fields = ["order", "amount", "reason"]
