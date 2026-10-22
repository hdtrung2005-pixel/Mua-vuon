"""
Review — đánh giá sản phẩm.

Quyết định thiết kế: khách chỉ được đánh giá sản phẩm ĐÃ MUA (kiểm tra qua
OrderItem ở service layer, không phải ở model — model chỉ enforce unique
1 review/user/product). ADMIN có thể ẩn review vi phạm qua is_approved.
"""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import BaseModel
from apps.products.models import Product


class Review(BaseModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    content = models.TextField(blank=True)
    image = models.ImageField(upload_to="reviews/", blank=True, null=True)
    is_approved = models.BooleanField(default=True, help_text="ADMIN tắt để ẩn review vi phạm.")

    class Meta:
        verbose_name = "đánh giá"
        verbose_name_plural = "đánh giá"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["product", "user"], name="unique_review_per_user_product"),
        ]

    def __str__(self):
        return f"{self.rating}★ — {self.product.name} bởi {self.user.email}"
