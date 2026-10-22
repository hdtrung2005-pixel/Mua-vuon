"""
Models cho Catalog: Category, Product, ProductImage.

Ghi chú thiết kế:
- Category.parent dùng self-FK để làm danh mục con (tree 1 cấp cha-con,
  đủ dùng cho nông sản: ví dụ "Rau củ" > "Rau ăn lá").
- Product không lưu category name trực tiếp — join qua FK, tối ưu bằng
  select_related ở tầng service/view, không lặp lại logic ở đây.
- Giá dùng DecimalField (không dùng Float) để tránh sai số khi tính tiền.
"""
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify

from apps.core.models import BaseModel


class Category(BaseModel):
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        help_text="Danh mục cha — để trống nếu là danh mục gốc.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "danh mục"
        verbose_name_plural = "danh mục"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ProductStatus(models.TextChoices):
    DRAFT = "DRAFT", "Bản nháp"
    ACTIVE = "ACTIVE", "Đang bán"
    OUT_OF_STOCK = "OUT_OF_STOCK", "Hết hàng"
    DISCONTINUED = "DISCONTINUED", "Ngừng kinh doanh"


class Product(BaseModel):
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products"
    )
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    description = models.TextField(blank=True)

    price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    discount_price = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    unit = models.CharField(max_length=30, help_text="Đơn vị tính, ví dụ: kg, bó, thùng.")

    origin = models.CharField(max_length=150, blank=True, help_text="Xuất xứ / nguồn gốc.")
    status = models.CharField(max_length=20, choices=ProductStatus.choices, default=ProductStatus.DRAFT)

    class Meta:
        verbose_name = "sản phẩm"
        verbose_name_plural = "sản phẩm"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["category", "status"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.name}-{self.sku}")
        super().save(*args, **kwargs)

    @property
    def effective_price(self):
        """Giá thực tế khách phải trả — ưu tiên giá khuyến mãi nếu có."""
        return self.discount_price if self.discount_price else self.price

    @property
    def is_purchasable(self):
        return self.status == ProductStatus.ACTIVE


class ProductImage(BaseModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/")
    is_primary = models.BooleanField(default=False)

    class Meta:
        verbose_name = "ảnh sản phẩm"
        verbose_name_plural = "ảnh sản phẩm"
        ordering = ["-is_primary", "-created_at"]

    def __str__(self):
        return f"Ảnh của {self.product.name}"


class Wishlist(BaseModel):
    """Sản phẩm yêu thích — khách lưu lại để xem/mua sau. 1 user không lưu trùng 1 sản phẩm."""

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="wishlist_items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="wishlisted_by")

    class Meta:
        verbose_name = "yêu thích"
        verbose_name_plural = "yêu thích"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="unique_wishlist_per_user_product"),
        ]

    def __str__(self):
        return f"{self.user.email} thích {self.product.name}"
