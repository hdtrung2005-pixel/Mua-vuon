"""
Models cho Inventory — Tồn kho.

Quyết định thiết kế:
- Inventory là OneToOne với Product: mỗi sản phẩm có đúng 1 dòng tồn kho.
- Mọi thay đổi số lượng (nhập/xuất/điều chỉnh) đều PHẢI đi qua service layer
  (apps/inventory/services.py) — không sửa trực tiếp Inventory.quantity ở
  view/admin, để đảm bảo luôn có InventoryTransaction ghi lại lịch sử và
  luôn dùng select_for_update() khi có race condition.
"""
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import BaseModel
from apps.products.models import Product


class Inventory(BaseModel):
    product = models.OneToOneField(Product, on_delete=models.PROTECT, related_name="inventory")
    quantity = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0)])
    low_stock_threshold = models.PositiveIntegerField(
        default=10, help_text="Dưới ngưỡng này sẽ được đánh dấu 'sắp hết hàng'."
    )

    class Meta:
        verbose_name = "tồn kho"
        verbose_name_plural = "tồn kho"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Tồn kho {self.product.name}: {self.quantity}"

    @property
    def is_low_stock(self) -> bool:
        return 0 < self.quantity <= self.low_stock_threshold

    @property
    def is_out_of_stock(self) -> bool:
        return self.quantity == 0


class TransactionType(models.TextChoices):
    IN = "IN", "Nhập kho"
    OUT = "OUT", "Xuất kho"
    ADJUST = "ADJUST", "Điều chỉnh kiểm kê"


class ReferenceType(models.TextChoices):
    ORDER = "ORDER", "Đơn hàng"
    PURCHASE_ORDER = "PURCHASE_ORDER", "Đơn nhập hàng"
    MANUAL = "MANUAL", "Điều chỉnh thủ công"
    RETURN = "RETURN", "Hoàn hàng"


class InventoryTransaction(BaseModel):
    """
    Lịch sử biến động kho — mỗi lần nhập/xuất/điều chỉnh đều tạo 1 dòng ở đây.
    KHÔNG cho sửa/xóa sau khi tạo (immutable log), chỉ có thể tạo thêm giao
    dịch điều chỉnh ngược lại nếu nhập sai.
    """

    inventory = models.ForeignKey(Inventory, on_delete=models.PROTECT, related_name="transactions")
    transaction_type = models.CharField(max_length=10, choices=TransactionType.choices)
    quantity = models.IntegerField(
        help_text="Số lượng thay đổi. IN/dương khi nhập, OUT lưu số dương nhưng trừ khỏi kho."
    )
    reference_type = models.CharField(max_length=20, choices=ReferenceType.choices, default=ReferenceType.MANUAL)
    reference_id = models.CharField(max_length=50, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="inventory_transactions"
    )

    class Meta:
        verbose_name = "lịch sử kho"
        verbose_name_plural = "lịch sử kho"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["inventory", "-created_at"])]

    def __str__(self):
        return f"{self.transaction_type} {self.quantity} — {self.inventory.product.name}"
