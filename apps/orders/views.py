"""API đơn hàng — /api/v1/orders/..."""
from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError
from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.inventory.services import InsufficientStockError
from apps.orders import services
from apps.orders.models import Order
from apps.orders.serializers import (
    CancelOrderInputSerializer,
    CheckoutInputSerializer,
    OrderSerializer,
)
from apps.orders.services import EmptyCartError, OrderNotCancellableError


class OrderListView(generics.ListAPIView):
    """Lịch sử đặt hàng của chính khách hàng (STAFF/ADMIN xem toàn bộ ở Phase Dashboard sau)."""

    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Order.objects.filter(customer=self.request.user)
            .select_related("payment", "shipping")
            .prefetch_related("items")
            .order_by("-created_at")
        )


class OrderDetailView(generics.RetrieveAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "order_code"

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user).select_related("payment", "shipping").prefetch_related("items")


class CheckoutView(APIView):
    """
    POST /api/v1/orders/checkout/
    Body: {address_id, shipping_fee?, discount?, payment_method?, note?}
    Đặt hàng từ các sản phẩm đang được chọn (selected=True) trong giỏ.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CheckoutInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            order = services.checkout(
                user=request.user,
                address_id=data["address_id"],
                shipping_fee=data["shipping_fee"],
                discount=data["discount"],
                payment_method=data["payment_method"],
                note=data["note"],
            )
        except ObjectDoesNotExist:
            raise NotFound("Không tìm thấy địa chỉ giao hàng — kiểm tra lại address_id.")
        except EmptyCartError as exc:
            raise DRFValidationError({"detail": str(exc)})
        except InsufficientStockError as exc:
            # Thông báo thân thiện, không lộ chi tiết kỹ thuật — đúng chuẩn error handling đã chốt.
            raise DRFValidationError({"detail": "Sản phẩm không đủ số lượng trong kho."})
        except DjangoValidationError as exc:
            raise DRFValidationError({"detail": exc.messages if hasattr(exc, "messages") else str(exc)})

        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class CancelOrderView(APIView):
    """POST /api/v1/orders/<order_code>/cancel/ — Body: {reason?}"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_code):
        serializer = CancelOrderInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = generics.get_object_or_404(Order, order_code=order_code, customer=request.user)
        try:
            order = services.cancel_order(request.user, order.id, reason=serializer.validated_data["reason"])
        except OrderNotCancellableError as exc:
            raise DRFValidationError({"detail": str(exc)})

        return Response(OrderSerializer(order).data)
