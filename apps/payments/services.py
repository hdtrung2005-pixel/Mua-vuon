"""Service layer cho Payment."""
from django.utils import timezone

from apps.payments.models import Payment, PaymentStatus


def create_payment_for_order(order, method="COD"):
    """Tạo Payment PENDING ngay khi Order được tạo (gọi từ orders.services.checkout)."""
    return Payment.objects.create(order=order, amount=order.final_amount, method=method)


def mark_payment_success(order_id, transaction_id=""):
    payment = Payment.objects.select_related("order").get(order_id=order_id)
    payment.status = PaymentStatus.SUCCESS
    payment.transaction_id = transaction_id
    payment.paid_at = timezone.now()
    payment.save(update_fields=["status", "transaction_id", "paid_at", "updated_at"])
    return payment


def mark_payment_failed(order_id, reason=""):
    payment = Payment.objects.select_related("order").get(order_id=order_id)
    payment.status = PaymentStatus.FAILED
    payment.save(update_fields=["status", "updated_at"])
    return payment
