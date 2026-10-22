"""RefundRequest — yêu cầu hoàn tiền. Khách chỉ được gửi cho đơn của chính mình."""
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import BaseModel
from apps.orders.models import Order


class RefundStatus(models.TextChoices):
    REQUESTED = "REQUESTED", "Đã yêu cầu"
    APPROVED = "APPROVED", "Đã duyệt"
    REJECTED = "REJECTED", "Đã từ chối"
    PROCESSING = "PROCESSING", "Đang xử lý"
    COMPLETED = "COMPLETED", "Hoàn tất"


class RefundRequest(BaseModel):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="refund_requests")
    reason = models.TextField()
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    proof_image = models.ImageField(upload_to="refunds/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=RefundStatus.choices, default=RefundStatus.REQUESTED)
    processed_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="processed_refunds"
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    staff_note = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "yêu cầu hoàn tiền"
        verbose_name_plural = "yêu cầu hoàn tiền"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Hoàn tiền {self.order.order_code} — {self.status}"
