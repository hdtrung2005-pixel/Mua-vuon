"""
config/urls.py — tổng hợp toàn bộ route của dự án.

Quy ước:
- /admin/            → Django Admin
- /accounts/...      → SSR (session auth): login/logout web
- /api/v1/auth/...   → REST API (JWT): register/login/refresh/me
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.urls import api_urlpatterns as accounts_api_urls

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("api/v1/auth/", include((accounts_api_urls, "accounts"), namespace="accounts-api")),
    path("api/v1/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/v1/", include("apps.products.urls")),
    path("api/v1/inventory/", include("apps.inventory.urls")),
    path("api/v1/cart/", include("apps.cart.urls")),
    path("api/v1/orders/", include("apps.orders.urls")),
    path("api/v1/payments/", include("apps.payments.urls")),
    path("api/v1/shipping/", include("apps.shipping.urls")),
    path("api/v1/refunds/", include("apps.refunds.urls")),
    path("api/v1/reviews/", include("apps.reviews.urls")),
    path("", include("apps.storefront.urls")),
    path("quan-ly/", include("apps.staffpanel.urls")),
]

if settings.DEBUG:
    # Chỉ dùng cách này ở local dev — production phải serve media qua Nginx/CDN riêng.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
