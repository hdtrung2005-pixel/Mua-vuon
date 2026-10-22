"""
Shipping — vận chuyển. STAFF cập nhật trạng thái giao hàng (không có role
Shipper riêng — đã chốt từ đầu, STAFF thao tác thay).
"""
import uuid

from django.db import models

from apps.core.models import BaseModel
from apps.orders.models import Order


class ShippingStatus(models.TextChoices):
    WAITING_PICKUP = "WAITING_PICKUP", "Chờ lấy hàng"
    PICKED_UP = "PICKED_UP", "Đã lấy hàng"
    IN_TRANSIT = "IN_TRANSIT", "Đang vận chuyển"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY", "Đang giao"
    DELIVERED = "DELIVERED", "Đã giao"
    FAILED = "FAILED", "Giao thất bại"
    RETURNING = "RETURNING", "Đang hoàn về"
    RETURNED = "RETURNED", "Đã hoàn về"


def generate_tracking_code():
    return f"SHIP-{uuid.uuid4().hex[:10].upper()}"


class Shipping(BaseModel):
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="shipping")
    tracking_code = models.CharField(max_length=20, unique=True, default=generate_tracking_code)
    shipping_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=ShippingStatus.choices, default=ShippingStatus.WAITING_PICKUP)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "vận chuyển"
        verbose_name_plural = "vận chuyển"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tracking_code} — {self.status}"
