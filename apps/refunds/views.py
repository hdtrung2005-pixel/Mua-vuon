"""API RefundRequest — Customer tạo yêu cầu cho đơn của mình, STAFF/ADMIN duyệt/từ chối/hoàn tất."""
from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError
from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaffRole
from apps.refunds import services
from apps.refunds.models import RefundRequest
from apps.refunds.serializers import (
    CreateRefundRequestSerializer,
    ProcessRefundSerializer,
    RefundRequestSerializer,
)


class MyRefundRequestListView(generics.ListAPIView):
    """Customer xem lịch sử yêu cầu hoàn tiền của chính mình."""

    serializer_class = RefundRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return RefundRequest.objects.filter(order__customer=self.request.user).select_related("order")


class CreateRefundRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CreateRefundRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            refund = services.request_refund(request.user, **serializer.validated_data)
        except ObjectDoesNotExist:
            raise NotFound("Không tìm thấy đơn hàng.")
        except DjangoValidationError as exc:
            raise DRFValidationError({"detail": exc.messages if hasattr(exc, "messages") else str(exc)})
        return Response(RefundRequestSerializer(refund).data, status=status.HTTP_201_CREATED)


class StaffRefundRequestListView(generics.ListAPIView):
    """STAFF/ADMIN xem toàn bộ yêu cầu hoàn tiền để xử lý."""

    serializer_class = RefundRequestSerializer
    permission_classes = [IsStaffRole]
    queryset = RefundRequest.objects.select_related("order").order_by("-created_at")


def _process_action(request, refund_id, service_fn):
    serializer = ProcessRefundSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        refund = service_fn(refund_id, request.user, note=serializer.validated_data["note"])
    except ObjectDoesNotExist:
        raise NotFound("Không tìm thấy yêu cầu hoàn tiền.")
    except DjangoValidationError as exc:
        raise DRFValidationError({"detail": exc.messages if hasattr(exc, "messages") else str(exc)})
    return Response(RefundRequestSerializer(refund).data)


class ApproveRefundView(APIView):
    permission_classes = [IsStaffRole]

    def post(self, request, refund_id):
        return _process_action(request, refund_id, services.approve_refund)


class RejectRefundView(APIView):
    permission_classes = [IsStaffRole]

    def post(self, request, refund_id):
        return _process_action(request, refund_id, services.reject_refund)


class CompleteRefundView(APIView):
    permission_classes = [IsStaffRole]

    def post(self, request, refund_id):
        return _process_action(request, refund_id, services.complete_refund)
