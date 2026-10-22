"""
Tự động xóa cache khi Category/Product thay đổi.
Đăng ký ở apps.py (ready()) để chắc chắn signal được load khi Django khởi động.
"""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.products.models import Category, Product
from apps.products.services import invalidate_category_cache, invalidate_homepage_products_cache


@receiver([post_save, post_delete], sender=Category)
def clear_category_cache(sender, **kwargs):
    invalidate_category_cache()


@receiver([post_save, post_delete], sender=Product)
def clear_product_cache(sender, **kwargs):
    invalidate_homepage_products_cache()
