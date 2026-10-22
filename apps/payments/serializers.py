from rest_framework import serializers

from apps.payments.models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    order_code = serializers.CharField(source="order.order_code", read_only=True)

    class Meta:
        model = Payment
        fields = ["id", "order", "order_code", "amount", "method", "status", "transaction_id", "paid_at"]
        read_only_fields = fields  # chỉ đổi qua services, không cho PATCH tuỳ ý
