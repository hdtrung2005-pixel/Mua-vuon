"""API giỏ hàng — /api/v1/cart/...  Chỉ user đã đăng nhập (mọi role đều có giỏ riêng)."""
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cart import services
from apps.cart.serializers import (
    AddItemInputSerializer,
    CartSerializer,
    ToggleSelectedInputSerializer,
    UpdateQuantityInputSerializer,
)


def _to_drf_error(exc: DjangoValidationError):
    """Chuyển ValidationError của Django (dùng ở service layer) sang lỗi DRF chuẩn."""
    return DRFValidationError({"detail": exc.messages if hasattr(exc, "messages") else str(exc)})


class CartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        cart = services.get_or_create_cart(request.user)
        return Response(CartSerializer(cart).data)


class AddCartItemView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = AddItemInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.add_item(request.user, **serializer.validated_data)
        except DjangoValidationError as exc:
            raise _to_drf_error(exc)
        cart = services.get_or_create_cart(request.user)
        return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED)


class CartItemDetailView(APIView):
    """PATCH để đổi số lượng hoặc selected, DELETE để xóa khỏi giỏ."""

    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, item_id):
        if "quantity" in request.data:
            serializer = UpdateQuantityInputSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            try:
                services.update_item_quantity(request.user, item_id, serializer.validated_data["quantity"])
            except DjangoValidationError as exc:
                raise _to_drf_error(exc)

        if "selected" in request.data:
            serializer = ToggleSelectedInputSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            services.toggle_selected(request.user, item_id, serializer.validated_data["selected"])

        cart = services.get_or_create_cart(request.user)
        return Response(CartSerializer(cart).data)

    def delete(self, request, item_id):
        services.remove_item(request.user, item_id)
        cart = services.get_or_create_cart(request.user)
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)
