"""Serializers cho /api/v1/auth/ — dùng JWT."""
from django.contrib.auth import password_validation
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.models import Address, Role, User


class UserSerializer(serializers.ModelSerializer):
    """Thông tin user trả về cho client (không bao giờ lộ password)."""

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "phone", "avatar", "role", "is_verified", "created_at"]
        read_only_fields = ["id", "role", "is_verified", "created_at"]


class RegisterSerializer(serializers.ModelSerializer):
    """
    Đăng ký tài khoản qua API — chỉ cho phép tạo role CUSTOMER.
    Role ADMIN/STAFF chỉ được tạo qua Django Admin hoặc script seed,
    tuyệt đối không expose qua API đăng ký công khai.
    """

    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["email", "full_name", "phone", "password", "password_confirm"]

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Mật khẩu xác nhận không khớp."})
        password_validation.validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        user = User.objects.create_user(role=Role.CUSTOMER, password=password, **validated_data)
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Mở rộng JWT payload để FE không cần gọi thêm API lấy role sau khi login.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["email"] = user.email
        token["full_name"] = user.full_name
        return token


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            "id", "full_name", "phone", "province", "district",
            "ward", "detail", "note", "is_default", "created_at",
        ]
        read_only_fields = ["id", "is_default", "created_at"]
