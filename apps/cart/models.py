"""
Cart & CartItem — giỏ hàng.

Thiết kế: mỗi User có đúng 1 Cart (OneToOne), CartItem là các dòng sản phẩm
trong giỏ. Số lượng/tổng tiền được TÍNH TOÁN (property), không lưu cứng
total_amount ở Cart — tránh lệch dữ liệu khi giá sản phẩm thay đổi trước
khi checkout (chỉ snapshot giá tại Order, không snapshot ở Cart).
"""
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import BaseModel
from apps.products.models import Product


class Cart(BaseModel):
    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, related_name="cart")

    class Meta:
        verbose_name = "giỏ hàng"
        verbose_name_plural = "giỏ hàng"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Giỏ hàng của {self.user.email}"

    @property
    def selected_items(self):
        return self.items.filter(selected=True).select_related("product")

    @property
    def total_amount(self):
        return sum(item.subtotal for item in self.selected_items)


class CartItem(BaseModel):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="cart_items")
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    selected = models.BooleanField(default=True, help_text="Có chọn để checkout hay không.")

    class Meta:
        verbose_name = "sản phẩm trong giỏ"
        verbose_name_plural = "sản phẩm trong giỏ"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["cart", "product"], name="unique_product_per_cart"),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    @property
    def subtotal(self):
        return self.product.effective_price * self.quantity
