"""API Shipping — STAFF/ADMIN cập nhật trạng thái, Customer chỉ xem đơn của mình (qua OrderDetail, nối sau)."""
from rest_framework import generics, status as http_status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaffRole
from apps.shipping.models import Shipping
from apps.shipping.serializers import ShippingSerializer, UpdateShippingStatusSerializer
from apps.shipping.services import InvalidShippingTransitionError, update_shipping_status


class ShippingListView(generics.ListAPIView):
    """Danh sách vận chuyển — dùng cho Shipper Dashboard (STAFF thao tác thay)."""

    serializer_class = ShippingSerializer
    permission_classes = [IsStaffRole]

    def get_queryset(self):
        qs = Shipping.objects.select_related("order").order_by("-created_at")
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


class UpdateShippingStatusView(APIView):
    """POST /api/v1/shipping/<id>/update-status/  Body: {status, note?}"""

    permission_classes = [IsStaffRole]

    def post(self, request, shipping_id):
        serializer = UpdateShippingStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            shipping = update_shipping_status(
                shipping_id,
                serializer.validated_data["status"],
                user=request.user,
                note=serializer.validated_data["note"],
            )
        except InvalidShippingTransitionError as exc:
            raise DRFValidationError({"detail": str(exc)})

        return Response(ShippingSerializer(shipping).data, status=http_status.HTTP_200_OK)
