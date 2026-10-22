"""
URL cho accounts app.

Lưu ý: file này chỉ khai báo route cục bộ của app. Việc gắn tiền tố
/api/v1/ và /accounts/ được thực hiện ở config/urls.py (nơi tổng hợp
toàn bộ route của dự án) — giúp accounts/urls.py có thể tái sử dụng
độc lập nếu cần.
"""
from django.urls import path

from apps.accounts import views

app_name = "accounts"

# --- Web (SSR / Session) ---
web_urlpatterns = [
    path("login/", views.SessionLoginView.as_view(), name="login"),
    path("logout/", views.SessionLogoutView.as_view(), name="logout"),
]

# --- API (JWT) ---
api_urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="api-register"),
    path("login/", views.CustomTokenObtainPairView.as_view(), name="api-login"),
    path("me/", views.MeView.as_view(), name="api-me"),
    path("addresses/", views.AddressListCreateView.as_view(), name="api-address-list"),
    path("addresses/<int:pk>/", views.AddressDetailView.as_view(), name="api-address-detail"),
    path("addresses/<int:pk>/set-default/", views.SetDefaultAddressView.as_view(), name="api-address-set-default"),
]

urlpatterns = web_urlpatterns
