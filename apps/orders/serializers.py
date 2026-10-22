from rest_framework import serializers

from apps.orders.models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product", "product_name_snapshot", "quantity", "price_at_purchase", "subtotal"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    shipping_address = serializers.DictField(read_only=True)
    is_cancellable = serializers.BooleanField(read_only=True)
    payment_status = serializers.SerializerMethodField()
    shipping_status = serializers.SerializerMethodField()
    tracking_code = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id", "order_code", "status", "items",
            "total_amount", "shipping_fee", "discount", "final_amount",
            "shipping_address", "payment_method", "payment_status",
            "tracking_code", "shipping_status", "note",
            "is_cancellable", "created_at",
        ]
        read_only_fields = fields

    def get_payment_status(self, obj):
        return obj.payment.status if hasattr(obj, "payment") else None

    def get_shipping_status(self, obj):
        return obj.shipping.status if hasattr(obj, "shipping") else None

    def get_tracking_code(self, obj):
        return obj.shipping.tracking_code if hasattr(obj, "shipping") else None


class CheckoutInputSerializer(serializers.Serializer):
    address_id = serializers.IntegerField()
    shipping_fee = serializers.DecimalField(max_digits=12, decimal_places=2, default=0, min_value=0)
    discount = serializers.DecimalField(max_digits=12, decimal_places=2, default=0, min_value=0)
    payment_method = serializers.ChoiceField(choices=["COD", "BANK_TRANSFER"], default="COD")
    note = serializers.CharField(required=False, allow_blank=True, default="")


class CancelOrderInputSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, default="")
