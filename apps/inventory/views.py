"""
API cho Inventory — CHỈ STAFF/ADMIN được truy cập (đúng RBAC đã chốt:
Customer không được xem/sửa tồn kho).
"""
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaffRole
from apps.inventory.models import Inventory, InventoryTransaction
from apps.inventory.serializers import (
    AdjustStockSerializer,
    InventorySerializer,
    InventoryTransactionSerializer,
    ReceiveStockSerializer,
)
from apps.inventory.services import InsufficientStockError, adjust_stock, receive_stock


class InventoryListView(generics.ListAPIView):
    """Danh sách tồn kho toàn bộ sản phẩm — dùng cho Warehouse Dashboard."""

    serializer_class = InventorySerializer
    permission_classes = [IsStaffRole]
    queryset = Inventory.objects.select_related("product").order_by("product__name")


class InventoryTransactionListView(generics.ListAPIView):
    """Lịch sử biến động kho — filter theo ?inventory=<id>."""

    serializer_class = InventoryTransactionSerializer
    permission_classes = [IsStaffRole]

    def get_queryset(self):
        qs = InventoryTransaction.objects.select_related("inventory__product", "created_by")
        inventory_id = self.request.query_params.get("inventory")
        if inventory_id:
            qs = qs.filter(inventory_id=inventory_id)
        return qs.order_by("-created_at")


class ReceiveStockView(APIView):
    """STAFF nhập kho: POST {product_id, quantity, note}."""

    permission_classes = [IsStaffRole]

    def post(self, request):
        serializer = ReceiveStockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        get_object_or_404(Inventory, product_id=data["product_id"])  # 404 rõ ràng nếu sai product_id
        inventory = receive_stock(
            product_id=data["product_id"],
            quantity=data["quantity"],
            user=request.user,
            note=data["note"],
        )
        return Response(InventorySerializer(inventory).data, status=status.HTTP_200_OK)


class AdjustStockView(APIView):
    """STAFF điều chỉnh tồn kho sau kiểm kê: POST {product_id, new_quantity, note}."""

    permission_classes = [IsStaffRole]

    def post(self, request):
        serializer = AdjustStockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        get_object_or_404(Inventory, product_id=data["product_id"])
        inventory = adjust_stock(
            product_id=data["product_id"],
            new_quantity=data["new_quantity"],
            user=request.user,
            note=data["note"],
        )
        return Response(InventorySerializer(inventory).data, status=status.HTTP_200_OK)
