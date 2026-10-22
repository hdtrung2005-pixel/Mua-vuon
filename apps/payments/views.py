"""API Payment — chỉ STAFF/ADMIN xem/xác nhận (Customer xem qua OrderSerializer nếu cần, phase sau nối)."""
from rest_framework import generics

from apps.accounts.permissions import IsStaffRole
from apps.payments.models import Payment
from apps.payments.serializers import PaymentSerializer


class PaymentListView(generics.ListAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [IsStaffRole]
    queryset = Payment.objects.select_related("order").order_by("-created_at")
