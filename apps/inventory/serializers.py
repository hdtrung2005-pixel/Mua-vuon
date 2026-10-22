from rest_framework import serializers

from apps.inventory.models import Inventory, InventoryTransaction


class InventorySerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)
    is_out_of_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Inventory
        fields = [
            "id", "product", "product_name", "product_sku",
            "quantity", "low_stock_threshold", "is_low_stock", "is_out_of_stock",
        ]
        read_only_fields = ["quantity"]  # quantity CHỈ đổi qua services, không cho PATCH trực tiếp


class InventoryTransactionSerializer(serializers.ModelSerializer):
    created_by_email = serializers.CharField(source="created_by.email", read_only=True, default=None)

    class Meta:
        model = InventoryTransaction
        fields = [
            "id", "inventory", "transaction_type", "quantity",
            "reference_type", "reference_id", "note", "created_by_email", "created_at",
        ]
        read_only_fields = fields  # log lịch sử — không cho sửa qua API


# --- Serializer cho các action nhập/xuất/điều chỉnh (input, không map trực tiếp model) ---


class ReceiveStockSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)
    note = serializers.CharField(required=False, allow_blank=True, default="")


class AdjustStockSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    new_quantity = serializers.IntegerField(min_value=0)
    note = serializers.CharField(required=False, allow_blank=True, default="")
