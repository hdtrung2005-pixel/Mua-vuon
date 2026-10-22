"""Settings chỉ dùng để test nhanh trong sandbox — KHÔNG dùng cho dev/prod thật."""
from .base import *  # noqa

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db_test.sqlite3",
        # timeout cao hơn mặc định (5s) vì test concurrency ở apps/inventory
        # dùng nhiều thread cùng ghi — SQLite cần đợi lock lâu hơn Postgres/SQL Server thật.
        "OPTIONS": {"timeout": 60},
    }
}

ALLOWED_HOSTS = ["*"]  # test client dùng host "testserver" — nới lỏng vì đây chỉ chạy trong CI/local test

# Test không cần Redis thật — dùng local memory cache để chạy nhanh và độc lập môi trường.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
