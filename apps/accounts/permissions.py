"""
RBAC — permission classes cho DRF + decorator cho view SSR.

Nguyên tắc: KHÔNG chỉ ẩn nút trên frontend. Mọi kiểm tra quyền phải
nằm ở đây (backend), trả 403 rõ ràng thay vì để lỗi 500/lộ dữ liệu.
"""
from functools import wraps

from django.core.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from apps.accounts.models import Role

# ---------------------------------------------------------------------------
# DRF Permission classes (dùng cho API /api/v1/...)
# ---------------------------------------------------------------------------


class IsAdmin(BasePermission):
    message = "Chỉ Quản trị viên được thực hiện thao tác này."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == Role.ADMIN)


class IsStaffRole(BasePermission):
    """STAFF hoặc ADMIN (ADMIN luôn có quyền của STAFF)."""

    message = "Chỉ Nhân viên vận hành hoặc Quản trị viên được thực hiện thao tác này."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_operational_staff
        )


class IsCustomer(BasePermission):
    message = "Chức năng này chỉ dành cho Khách hàng."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == Role.CUSTOMER)


class IsOwnerOrStaff(BasePermission):
    """
    Cho phép chủ sở hữu object (obj.user == request.user) hoặc STAFF/ADMIN.
    Dùng cho các resource cá nhân như Order, Address, Review...
    """

    message = "Bạn không có quyền truy cập tài nguyên này."

    def has_object_permission(self, request, view, obj):
        if request.user.is_operational_staff:
            return True
        owner = getattr(obj, "user", None) or getattr(obj, "customer", None)
        return owner == request.user


# ---------------------------------------------------------------------------
# Decorator cho SSR views (function-based views render HTML)
# ---------------------------------------------------------------------------


def require_role(*allowed_roles):
    """
    Decorator cho view SSR: chặn truy cập nếu user không thuộc allowed_roles.
    Ném PermissionDenied (Django tự render trang 403.html) thay vì lỗi 500.

    Ví dụ:
        @require_role(Role.ADMIN, Role.STAFF)
        def inventory_dashboard(request): ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied("Vui lòng đăng nhập để tiếp tục.")
            if request.user.role not in allowed_roles:
                raise PermissionDenied("Bạn không có quyền truy cập trang này.")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
