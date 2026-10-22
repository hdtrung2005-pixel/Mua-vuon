"""Service layer cho RefundRequest — chỉ ADMIN được duyệt/từ chối (đúng RBAC đã chốt)."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.orders.models import OrderStatus
from apps.refunds.models import RefundRequest, RefundStatus

# Chỉ cho yêu cầu hoàn tiền khi đơn đã giao hoặc đã hủy — không cho hoàn tiền đơn còn đang xử lý bình thường.
REFUNDABLE_ORDER_STATUSES = {OrderStatus.DELIVERED, OrderStatus.CANCELLED}


def request_refund(user, order_id, reason, amount, proof_image=None):
    from apps.orders.models import Order

    order = Order.objects.get(id=order_id, customer=user)
    if order.status not in REFUNDABLE_ORDER_STATUSES:
        raise ValidationError(
            f"Đơn hàng ở trạng thái '{order.status}' chưa thể yêu cầu hoàn tiền."
        )
    if amount > order.final_amount:
        raise ValidationError("Số tiền hoàn không được lớn hơn giá trị đơn hàng.")

    return RefundRequest.objects.create(
        order=order, reason=reason, amount=amount, proof_image=proof_image
    )


def approve_refund(refund_id, staff_user, note=""):
    with transaction.atomic():
        refund = RefundRequest.objects.select_for_update().get(id=refund_id)
        if refund.status != RefundStatus.REQUESTED:
            raise ValidationError(f"Yêu cầu đang ở trạng thái '{refund.status}', không thể duyệt.")
        refund.status = RefundStatus.APPROVED
        refund.processed_by = staff_user
        refund.processed_at = timezone.now()
        refund.staff_note = note
        refund.save()
    return refund


def reject_refund(refund_id, staff_user, note=""):
    with transaction.atomic():
        refund = RefundRequest.objects.select_for_update().get(id=refund_id)
        if refund.status != RefundStatus.REQUESTED:
            raise ValidationError(f"Yêu cầu đang ở trạng thái '{refund.status}', không thể từ chối.")
        refund.status = RefundStatus.REJECTED
        refund.processed_by = staff_user
        refund.processed_at = timezone.now()
        refund.staff_note = note
        refund.save()
    return refund


def complete_refund(refund_id, staff_user, note=""):
    """Sau khi đã chuyển tiền thật cho khách (ngoài hệ thống, vì Phase này chỉ có COD) — đánh dấu hoàn tất."""
    with transaction.atomic():
        refund = RefundRequest.objects.select_for_update().select_related("order").get(id=refund_id)
        if refund.status != RefundStatus.APPROVED:
            raise ValidationError(f"Yêu cầu phải ở trạng thái APPROVED mới có thể hoàn tất, hiện là '{refund.status}'.")
        refund.status = RefundStatus.COMPLETED
        refund.staff_note = note or refund.staff_note
        refund.save()

        refund.order.status = OrderStatus.REFUNDED
        refund.order.save(update_fields=["status", "updated_at"])
    return refund
