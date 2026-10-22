from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.accounts.models import Address, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Quản lý User trong Django Admin — đăng nhập bằng email, có filter theo role."""

    ordering = ["-created_at"]
    list_display = ["email", "full_name", "role", "is_active", "is_verified", "created_at"]
    list_filter = ["role", "is_active", "is_verified"]
    search_fields = ["email", "full_name", "phone"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Thông tin cá nhân", {"fields": ("full_name", "phone", "avatar")}),
        ("Phân quyền", {"fields": ("role", "is_active", "is_staff", "is_superuser", "is_verified", "groups", "user_permissions")}),
        ("Ngày quan trọng", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (None, {"fields": ("email", "role", "password1", "password2")}),
    )
    readonly_fields = ["created_at", "updated_at", "last_login"]


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ["user", "full_name", "province", "district", "is_default"]
    list_filter = ["is_default", "province"]
    search_fields = ["full_name", "phone", "user__email"]
