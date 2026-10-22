"""
Tự động tạo Inventory (quantity=0) khi Product mới được tạo — để không bao
giờ có Product thiếu Inventory (tránh DoesNotExist khi checkout/nhập kho).
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.inventory.models import Inventory
from apps.products.models import Product


@receiver(post_save, sender=Product)
def create_inventory_for_new_product(sender, instance, created, **kwargs):
    if created:
        Inventory.objects.get_or_create(product=instance)
