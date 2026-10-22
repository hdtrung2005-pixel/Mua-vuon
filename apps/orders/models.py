"""
Order & OrderItem.

Quyết định thiết kế quan trọng (đã chốt từ đầu prompt):
- price_at_purchase (OrderItem) và shipping_address_snapshot (Order) được
  COPY CỨNG tại thời điểm checkout. Sau đó dù Admin đổi giá sản phẩm hay
  khách đổi địa chỉ, đơn hàng cũ vẫn giữ nguyên — không tự đổi theo.
- shipping_address_snapshot lưu dạng TextField chứa JSON string (không
  dùng JSONField) để tương thích SQL Server qua mssql-django.
"""
import json
import uuid

from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import BaseModel
from apps.products.models import Product


class OrderStatus(models.TextChoices):
    PENDING = "PENDING", "Chờ xác nhận"
    CONFIRMED = "CONFIRMED", "Đã xác nhận"
    PROCESSING = "PROCESSING", "Đang xử lý"
    PACKING = "PACKING", "Đang đóng gói"
    SHIPPING = "SHIPPING", "Đang giao"
    DELIVERED = "DELIVERED", "Đã giao"
    CANCELLED = "CANCELLED", "Đã hủy"
    RETURN_REQUESTED = "RETURN_REQUESTED", "Yêu cầu hoàn hàng"
    RETURNED = "RETURNED", "Đã hoàn hàng"
    REFUNDED = "REFUNDED", "Đã hoàn tiền"


# Trạng thái mà khách còn được phép tự hủy đơn (chưa đóng gói/giao)
CANCELLABLE_STATUSES = {OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PROCESSING}


def generate_order_code():
    return f"ORD-{uuid.uuid4().hex[:10].upper()}"


class Order(BaseModel):
    order_code = models.CharField(max_length=20, unique=True, default=generate_order_code)
    customer = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="orders")

    total_amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    shipping_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    final_amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])

    # Snapshot địa chỉ — JSON string, KHÔNG FK tới Address (đề phòng Address bị xóa sau này)
    shipping_address_snapshot = models.TextField()

    payment_method = models.CharField(max_length=20, default="COD")
    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "đơn hàng"
        verbose_name_plural = "đơn hàng"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["customer", "-created_at"]), models.Index(fields=["status"])]

    def __str__(self):
        return f"{self.order_code} — {self.customer.email} — {self.status}"

    @property
    def shipping_address(self) -> dict:
        return json.loads(self.shipping_address_snapshot)

    @property
    def is_cancellable(self) -> bool:
        return self.status in CANCELLABLE_STATUSES


class OrderItem(BaseModel):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="items")
    # PROTECT: không cho xóa Product nếu đã từng có trong đơn hàng — giữ toàn vẹn lịch sử.
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    product_name_snapshot = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    price_at_purchase = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "chi tiết đơn hàng"
        verbose_name_plural = "chi tiết đơn hàng"
        ordering = ["id"]

    def __str__(self):
        return f"{self.quantity} x {self.product_name_snapshot}"

    @property
    def subtotal(self):
        return self.price_at_purchase * self.quantity
