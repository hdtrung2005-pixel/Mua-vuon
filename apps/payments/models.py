"""
Payment — thanh toán cho Order.

Thiết kế (đã chốt): tập trung vào COD ở phiên bản này, nhưng model để mở
sẵn cho VNPay/MoMo/ZaloPay/Stripe sau — chỉ cần thêm giá trị choices và
service xử lý callback, không cần đổi schema.
KHÔNG lưu thông tin thẻ ngân hàng nhạy cảm — chỉ lưu transaction_id do
cổng thanh toán trả về (tham chiếu, không phải dữ liệu thẻ).
"""
from django.db import models

from apps.core.models import BaseModel
from apps.orders.models import Order


class PaymentMethod(models.TextChoices):
    COD = "COD", "Thanh toán khi nhận hàng"
    BANK_TRANSFER = "BANK_TRANSFER", "Chuyển khoản ngân hàng"
    # Để sẵn cho tương lai — chưa xử lý logic ở phase này:
    VNPAY = "VNPAY", "VNPay"
    MOMO = "MOMO", "MoMo"
    ZALOPAY = "ZALOPAY", "ZaloPay"


class PaymentStatus(models.TextChoices):
    PENDING = "PENDING", "Chờ thanh toán"
    SUCCESS = "SUCCESS", "Thành công"
    FAILED = "FAILED", "Thất bại"


class Payment(BaseModel):
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="payment")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.COD)
    status = models.CharField(max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    transaction_id = models.CharField(max_length=100, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "thanh toán"
        verbose_name_plural = "thanh toán"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment {self.order.order_code} — {self.status}"
