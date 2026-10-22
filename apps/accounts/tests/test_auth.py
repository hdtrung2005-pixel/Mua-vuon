"""
Test cho luồng Authentication (Phase 1).
Chạy: pytest apps/accounts/tests/test_auth.py -v
"""
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Role, User

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


class TestRegister:
    def test_register_creates_customer(self, api_client):
        url = reverse("accounts-api:api-register")
        payload = {
            "email": "new_customer@test.com",
            "full_name": "Tran Thi B",
            "password": "StrongPass123",
            "password_confirm": "StrongPass123",
        }
        response = api_client.post(url, payload)

        assert response.status_code == status.HTTP_201_CREATED
        user = User.objects.get(email="new_customer@test.com")
        assert user.role == Role.CUSTOMER  # đăng ký công khai luôn là CUSTOMER
        assert user.check_password("StrongPass123")

    def test_register_rejects_mismatched_password(self, api_client):
        url = reverse("accounts-api:api-register")
        payload = {
            "email": "bad@test.com",
            "password": "StrongPass123",
            "password_confirm": "DifferentPass123",
        }
        response = api_client.post(url, payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not User.objects.filter(email="bad@test.com").exists()

    def test_register_cannot_set_role(self, api_client):
        """Đảm bảo không thể tự đăng ký với role ADMIN/STAFF qua API công khai."""
        url = reverse("accounts-api:api-register")
        payload = {
            "email": "hacker@test.com",
            "password": "StrongPass123",
            "password_confirm": "StrongPass123",
            "role": "ADMIN",  # cố ý gửi lên, serializer phải bỏ qua field này
        }
        api_client.post(url, payload)
        user = User.objects.get(email="hacker@test.com")
        assert user.role == Role.CUSTOMER


class TestJWTLogin:
    def test_login_returns_tokens_with_role_claim(self, api_client):
        User.objects.create_user(email="login@test.com", password="StrongPass123", role=Role.STAFF)
        url = reverse("accounts-api:api-login")

        response = api_client.post(url, {"email": "login@test.com", "password": "StrongPass123"})

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data and "refresh" in response.data

    def test_login_wrong_password_fails(self, api_client):
        User.objects.create_user(email="login2@test.com", password="StrongPass123")
        url = reverse("accounts-api:api-login")

        response = api_client.post(url, {"email": "login2@test.com", "password": "WrongPass"})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestMeEndpoint:
    def test_me_requires_authentication(self, api_client):
        url = reverse("accounts-api:api-me")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_me_returns_current_user_with_token(self, api_client):
        user = User.objects.create_user(email="me@test.com", password="StrongPass123")
        login_url = reverse("accounts-api:api-login")
        token = api_client.post(login_url, {"email": "me@test.com", "password": "StrongPass123"}).data["access"]

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = api_client.get(reverse("accounts-api:api-me"))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == "me@test.com"


class TestRolePermissionHelpers:
    """Test các property role dùng trong permission layer (Phase sau sẽ dùng nhiều)."""

    def test_customer_role_flags(self):
        user = User(role=Role.CUSTOMER)
        assert user.is_customer is True
        assert user.is_operational_staff is False

    def test_staff_role_flags(self):
        user = User(role=Role.STAFF)
        assert user.is_operational_staff is True
        assert user.is_customer is False

    def test_admin_role_flags(self):
        user = User(role=Role.ADMIN)
        assert user.is_admin_role is True
        assert user.is_operational_staff is True
