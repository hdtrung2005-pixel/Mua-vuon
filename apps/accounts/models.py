"""
Custom User model — 3 role: CUSTOMER, ADMIN, STAFF.

Quyết định thiết kế (đã thống nhất với người dùng):
- Đăng nhập bằng EMAIL, không dùng username.
- STAFF gộp chung mọi nghiệp vụ vận hành nội bộ (kho, xác nhận đơn, vận chuyển).
- Supplier / Shipper KHÔNG có tài khoản đăng nhập riêng ở giai đoạn này —
  họ chỉ là entity dữ liệu (model riêng ở app suppliers/shipping, sẽ làm ở
  phase sau); STAFF là người thao tác thay trên hệ thống.
"""
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.managers import UserManager
from apps.core.models import BaseModel


class Role(models.TextChoices):
    CUSTOMER = "CUSTOMER", _("Khách hàng")
    ADMIN = "ADMIN", _("Quản trị viên")
    STAFF = "STAFF", _("Nhân viên vận hành")


phone_validator = RegexValidator(
    regex=r"^0\d{9,10}$",
    message="Số điện thoại không hợp lệ (phải bắt đầu bằng 0, 10-11 số).",
)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User dùng email làm định danh đăng nhập.

    Không kế thừa apps.core.BaseModel vì AbstractBaseUser đã có cơ chế riêng;
    ta khai báo created_at/updated_at trực tiếp để tránh xung đột MRO.
    """

    email = models.EmailField(_("email"), unique=True)
    full_name = models.CharField(_("họ tên"), max_length=150, blank=True)
    phone = models.CharField(
        _("số điện thoại"), max_length=15, blank=True, validators=[phone_validator]
    )
    avatar = models.ImageField(_("ảnh đại diện"), upload_to="avatars/", blank=True, null=True)
    role = models.CharField(
        _("vai trò"), max_length=20, choices=Role.choices, default=Role.CUSTOMER
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(
        default=False, help_text=_("Cho phép đăng nhập vào Django Admin.")
    )
    is_verified = models.BooleanField(
        default=False, help_text=_("Đã xác thực email/OTP hay chưa.")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # createsuperuser sẽ chỉ hỏi email + password

    class Meta:
        verbose_name = _("người dùng")
        verbose_name_plural = _("người dùng")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email} ({self.role})"

    # --- Helper properties cho permission layer ---
    @property
    def is_customer(self) -> bool:
        return self.role == Role.CUSTOMER

    @property
    def is_admin_role(self) -> bool:
        return self.role == Role.ADMIN

    @property
    def is_operational_staff(self) -> bool:
        """
        True nếu user thuộc nhóm 'vận hành nội bộ' (ADMIN hoặc STAFF).
        Dùng khi cần kiểm tra nhanh 'có phải người của hệ thống không'
        mà không cần phân biệt cụ thể ADMIN/STAFF.
        """
        return self.role in (Role.ADMIN, Role.STAFF)


class Address(BaseModel):
    """
    Địa chỉ giao hàng của user. Một user có thể có nhiều địa chỉ,
    1 địa chỉ mặc định (is_default). Khi checkout, dữ liệu địa chỉ được
    SNAPSHOT (copy cứng thành text) vào Order — sửa/xóa Address sau đó
    không ảnh hưởng đơn hàng cũ.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses")
    full_name = models.CharField(_("họ tên người nhận"), max_length=150)
    phone = models.CharField(_("số điện thoại"), max_length=15, validators=[phone_validator])
    province = models.CharField(_("tỉnh/thành"), max_length=100)
    district = models.CharField(_("quận/huyện"), max_length=100)
    ward = models.CharField(_("phường/xã"), max_length=100)
    detail = models.CharField(_("địa chỉ chi tiết"), max_length=255)
    note = models.CharField(_("ghi chú"), max_length=255, blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        verbose_name = _("địa chỉ")
        verbose_name_plural = _("địa chỉ")
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return f"{self.full_name} — {self.detail}, {self.ward}, {self.district}, {self.province}"

    def save(self, *args, **kwargs):
        """Đảm bảo mỗi user chỉ có đúng 1 địa chỉ is_default=True."""
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(
                is_default=False
            )
        super().save(*args, **kwargs)

    def to_snapshot_dict(self):
        """Dữ liệu sẽ được lưu cứng (JSON) vào Order.shipping_address_snapshot."""
        return {
            "full_name": self.full_name,
            "phone": self.phone,
            "province": self.province,
            "district": self.district,
            "ward": self.ward,
            "detail": self.detail,
            "note": self.note,
        }
