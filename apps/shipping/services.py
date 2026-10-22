"""
Service layer cho Shipping — bao gồm state machine kiểm soát chuyển
trạng thái hợp lệ (không cho nhảy cóc, ví dụ không thể từ WAITING_PICKUP
nhảy thẳng lên DELIVERED mà bỏ qua các bước).
"""
from django.db import transaction

from apps.shipping.models import Shipping, ShippingStatus

# Sơ đồ chuyển trạng thái hợp lệ — key: trạng thái hiện tại, value: các trạng thái được phép chuyển tới.
ALLOWED_TRANSITIONS = {
    ShippingStatus.WAITING_PICKUP: {ShippingStatus.PICKED_UP, ShippingStatus.FAILED},
    ShippingStatus.PICKED_UP: {ShippingStatus.IN_TRANSIT, ShippingStatus.FAILED},
    ShippingStatus.IN_TRANSIT: {ShippingStatus.OUT_FOR_DELIVERY, ShippingStatus.FAILED},
    ShippingStatus.OUT_FOR_DELIVERY: {ShippingStatus.DELIVERED, ShippingStatus.FAILED},
    ShippingStatus.FAILED: {ShippingStatus.RETURNING, ShippingStatus.OUT_FOR_DELIVERY},  # thử giao lại hoặc hoàn về
    ShippingStatus.RETURNING: {ShippingStatus.RETURNED},
    ShippingStatus.DELIVERED: set(),  # trạng thái cuối, không đổi tiếp
    ShippingStatus.RETURNED: set(),
}


class InvalidShippingTransitionError(Exception):
    def __init__(self, current, target):
        super().__init__(f"Không thể chuyển trạng thái vận chuyển từ '{current}' sang '{target}'.")


def create_shipping_for_order(order, shipping_fee=0):
    """Tự tạo Shipping(WAITING_PICKUP) ngay khi Order được tạo."""
    return Shipping.objects.create(order=order, shipping_fee=shipping_fee)


def update_shipping_status(shipping_id, new_status, user=None, note=""):
    """
    Đổi trạng thái vận chuyển — kiểm tra hợp lệ qua ALLOWED_TRANSITIONS.
    Khi chuyển sang DELIVERED: tự đồng bộ Order.status = DELIVERED và
    (nếu thanh toán COD) đánh dấu Payment.status = SUCCESS — đúng logic
    thực tế "khách trả tiền khi nhận hàng".
    """
    from django.utils import timezone

    from apps.orders.models import OrderStatus
    from apps.payments.models import PaymentMethod
    from apps.payments.services import mark_payment_success

    with transaction.atomic():
        shipping = Shipping.objects.select_related("order__payment").select_for_update().get(id=shipping_id)
        current = shipping.status

        if new_status not in ALLOWED_TRANSITIONS.get(current, set()):
            raise InvalidShippingTransitionError(current, new_status)

        shipping.status = new_status
        if note:
            shipping.note = note
        if new_status == ShippingStatus.PICKED_UP:
            shipping.picked_up_at = timezone.now()
        if new_status == ShippingStatus.DELIVERED:
            shipping.delivered_at = timezone.now()
        shipping.save()

        order = shipping.order
        if new_status == ShippingStatus.DELIVERED:
            order.status = OrderStatus.DELIVERED
            order.save(update_fields=["status", "updated_at"])
            if hasattr(order, "payment") and order.payment.method == PaymentMethod.COD:
                mark_payment_success(order.id, transaction_id=f"COD-{shipping.tracking_code}")

            from apps.products.services import invalidate_best_sellers_cache
            invalidate_best_sellers_cache()  # số liệu "bán chạy" đổi ngay khi có đơn giao thành công mới

    return shipping
