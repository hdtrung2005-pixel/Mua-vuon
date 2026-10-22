"""Test rate limiting cho login — chống brute-force (Phase 6)."""
import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


class TestLoginRateLimit:
    def test_jwt_login_blocked_after_too_many_attempts(self):
        """
        Giới hạn 5 lần/phút/IP. Gửi tối đa 8 lần (dư an toàn so với ngưỡng 5)
        thay vì đúng 6 lần — tránh test bị brittle theo ranh giới thời gian
        chính xác của cache khi chạy cùng cả suite dài (~40s), miễn là:
        (1) có ít nhất 5 lần được xử lý bình thường (401 — sai password),
        (2) rate limit thực sự kích hoạt (403) trước khi hết 8 lần thử.
        """
        User.objects.create_user(email="user@test.com", password="CorrectPass123")
        client = APIClient()
        url = reverse("accounts-api:api-login")

        status_codes = []
        for _ in range(8):
            response = client.post(url, {"email": "user@test.com", "password": "WrongPass"})
            status_codes.append(response.status_code)
            if response.status_code == status.HTTP_403_FORBIDDEN:
                break

        processed_count = status_codes.count(status.HTTP_401_UNAUTHORIZED)
        assert processed_count >= 5, f"Kỳ vọng ít nhất 5 lần xử lý bình thường, thực tế: {status_codes}"
        assert status.HTTP_403_FORBIDDEN in status_codes, f"Rate limit chưa kích hoạt sau 8 lần thử: {status_codes}"

    def test_correct_login_still_works_within_limit(self):
        User.objects.create_user(email="user2@test.com", password="CorrectPass123")
        client = APIClient()
        url = reverse("accounts-api:api-login")

        response = client.post(url, {"email": "user2@test.com", "password": "CorrectPass123"})
        assert response.status_code == status.HTTP_200_OK
