from rest_framework import serializers

from apps.refunds.models import RefundRequest


class RefundRequestSerializer(serializers.ModelSerializer):
    order_code = serializers.CharField(source="order.order_code", read_only=True)
    processed_by_email = serializers.CharField(source="processed_by.email", read_only=True, default=None)

    class Meta:
        model = RefundRequest
        fields = [
            "id", "order", "order_code", "reason", "amount", "proof_image",
            "status", "processed_by_email", "processed_at", "staff_note", "created_at",
        ]
        read_only_fields = ["status", "processed_by_email", "processed_at", "staff_note", "created_at"]


class CreateRefundRequestSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    reason = serializers.CharField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=0)


class ProcessRefundSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, default="")
