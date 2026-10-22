"""
Views cho accounts app.

- Phần API (/api/v1/auth/...): dùng JWT (SimpleJWT), trả JSON.
- Phần SSR (/accounts/...): dùng Session Auth, render template HTML,
  dành cho trang login/logout của Admin/Staff và web khách hàng cơ bản.
"""
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django_ratelimit.decorators import ratelimit
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.accounts.address_services import create_address, set_default_address
from apps.accounts.models import Address
from apps.accounts.serializers import (
    AddressSerializer,
    CustomTokenObtainPairSerializer,
    RegisterSerializer,
    UserSerializer,
)

# ---------------------------------------------------------------------------
# API views (JWT) — /api/v1/auth/...
# ---------------------------------------------------------------------------


class CustomTokenObtainPairView(TokenObtainPairView):
    """Login API — trả access + refresh token, payload có kèm role."""

    serializer_class = CustomTokenObtainPairSerializer

    @method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True))
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class RegisterView(generics.CreateAPIView):
    """Đăng ký tài khoản CUSTOMER qua API. Không cần đăng nhập."""

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    @method_decorator(ratelimit(key="ip", rate="10/h", method="POST", block=True))
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            UserSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


class MeView(APIView):
    """Xem / cập nhật thông tin user hiện tại — bắt buộc đăng nhập."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# SSR views (Session) — /accounts/...
# ---------------------------------------------------------------------------


class SessionLoginView(View):
    """
    Login cho web (Admin panel, Dashboard nội bộ, trang khách hàng cơ bản).
    Dùng session, KHÔNG liên quan JWT.
    """

    template_name = "accounts/login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("/")
        return render(request, self.template_name, {"form": AuthenticationForm()})

    def post(self, request):
        return self._rate_limited_post(request)

    @method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True))
    def _rate_limited_post(self, request):
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            django_login(request, form.get_user())
            next_url = request.POST.get("next") or "/"
            return redirect(next_url)
        # Thông báo lỗi thân thiện, không lộ chi tiết kỹ thuật
        return render(
            request,
            self.template_name,
            {"form": form, "error": "Email hoặc mật khẩu không chính xác."},
        )


class SessionLogoutView(LoginRequiredMixin, View):
    login_url = "accounts:login"

    def post(self, request):
        django_logout(request)
        return redirect("accounts:login")


# ---------------------------------------------------------------------------
# Address API — /api/v1/auth/addresses/...
# ---------------------------------------------------------------------------


class AddressListCreateView(generics.ListCreateAPIView):
    """Danh sách + tạo địa chỉ của user hiện tại (mỗi user chỉ thấy địa chỉ của mình)."""

    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        create_address(self.request.user, serializer.validated_data)


class AddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Sửa/xóa 1 địa chỉ — chỉ chủ sở hữu mới thao tác được (IsOwnerOrStaff)."""

    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)


class SetDefaultAddressView(APIView):
    """POST /addresses/<id>/set-default/ — đặt địa chỉ này làm mặc định."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        address = set_default_address(request.user, pk)
        return Response(AddressSerializer(address).data)
