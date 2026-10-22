"""
Service cho Address — đảm bảo mỗi user chỉ có đúng 1 địa chỉ is_default=True.
Đặt trong file riêng (không chung services.py) vì accounts app đã có nhiều
concern khác (auth); tách để dễ đọc — không bắt buộc nhưng tăng khả năng bảo trì.
"""
from django.db import transaction

from apps.accounts.models import Address


def set_default_address(user, address_id):
    """Đặt 1 địa chỉ làm mặc định — tự bỏ default ở các địa chỉ khác của user."""
    with transaction.atomic():
        Address.objects.filter(user=user, is_default=True).update(is_default=False)
        address = Address.objects.select_for_update().get(user=user, id=address_id)
        address.is_default = True
        address.save(update_fields=["is_default", "updated_at"])
    return address


def create_address(user, data: dict) -> Address:
    """
    Tạo địa chỉ mới. Nếu đây là địa chỉ đầu tiên của user, tự động set default
    (không để user phải thao tác thêm 1 bước mới có địa chỉ mặc định).
    """
    is_first_address = not Address.objects.filter(user=user).exists()
    address = Address.objects.create(user=user, is_default=is_first_address, **data)
    return address


def get_default_address(user):
    return Address.objects.filter(user=user, is_default=True).first()
