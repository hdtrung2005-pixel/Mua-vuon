from rest_framework import serializers

from apps.shipping.models import Shipping


class ShippingSerializer(serializers.ModelSerializer):
    order_code = serializers.CharField(source="order.order_code", read_only=True)

    class Meta:
        model = Shipping
        fields = [
            "id", "order", "order_code", "tracking_code", "shipping_fee",
            "status", "picked_up_at", "delivered_at", "note",
        ]
        read_only_fields = ["order", "order_code", "tracking_code", "picked_up_at", "delivered_at"]


class UpdateShippingStatusSerializer(serializers.Serializer):
    status = serializers.CharField()
    note = serializers.CharField(required=False, allow_blank=True, default="")
