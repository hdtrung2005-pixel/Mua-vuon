"""
Service checkout — nối Cart (Phase 4) với Inventory.reserve_stock (Phase 3).

Nguyên tắc:
- TOÀN BỘ checkout nằm trong 1 transaction.atomic() ở tầng ngoài. Nếu bất
  kỳ sản phẩm nào không đủ hàng (reserve_stock ném InsufficientStockError),
  toàn bộ đơn hàng — bao gồm các sản phẩm ĐÃ trừ kho thành công trước đó
  trong cùng lượt checkout — sẽ ROLLBACK hết, không tạo đơn "nửa vời".
- Giá + địa chỉ được snapshot NGAY tại đây, trước khi tạo OrderItem.
"""
import json

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import Address
from apps.cart.models import Cart
from apps.cart.services import get_or_create_cart
from apps.inventory.models import ReferenceType
from apps.inventory.services import InsufficientStockError, reserve_stock
from apps.orders.models import CANCELLABLE_STATUSES, Order, OrderItem, OrderStatus
from apps.payments.services import create_payment_for_order
from apps.products.models import ProductStatus
from apps.shipping.services import create_shipping_for_order


class EmptyCartError(Exception):
    pass


class OrderNotCancellableError(Exception):
    pass


def checkout(user, address_id, shipping_fee=0, discount=0, payment_method="COD", note=""):
    """
    Tạo Order từ các CartItem đang được `selected=True` trong giỏ của user.
    Trả về Order đã tạo, hoặc raise nếu giỏ trống / hết hàng / sai địa chỉ.
    """
    address = Address.objects.get(id=address_id, user=user)

    cart = get_or_create_cart(user)
    selected_items = list(
        cart.items.filter(selected=True).select_related("product").order_by("id")
    )
    if not selected_items:
        raise EmptyCartError("Giỏ hàng không có sản phẩm nào được chọn để đặt hàng.")

    with transaction.atomic():
        order = Order.objects.create(
            customer=user,
            total_amount=0,  # sẽ cập nhật sau khi có OrderItem
            shipping_fee=shipping_fee,
            discount=discount,
            final_amount=0,
            shipping_address_snapshot=json.dumps(address.to_snapshot_dict(), ensure_ascii=False),
            payment_method=payment_method,
            note=note,
        )

        total = 0
        for cart_item in selected_items:
            product = cart_item.product
            if product.status != ProductStatus.ACTIVE:
                raise ValidationError(f"Sản phẩm '{product.name}' hiện không thể mua.")

            # reserve_stock() tự mở transaction.atomic() riêng (savepoint) +
            # select_for_update() — nếu raise InsufficientStockError, exception
            # sẽ thoát ra ngoài, khiến atomic() bao ngoài rollback TOÀN BỘ đơn hàng.
            reserve_stock(
                product.id,
                cart_item.quantity,
                reference_type=ReferenceType.ORDER,
                reference_id=order.order_code,
                user=user,
                note=f"Trừ kho cho đơn {order.order_code}",
            )

            price = product.effective_price
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name_snapshot=product.name,
                quantity=cart_item.quantity,
                price_at_purchase=price,
            )
            total += price * cart_item.quantity

        order.total_amount = total
        order.final_amount = total + order.shipping_fee - order.discount
        order.save(update_fields=["total_amount", "final_amount"])

        # Tự tạo Payment (PENDING) + Shipping (WAITING_PICKUP) ngay khi đơn được tạo —
        # đúng luồng thực tế: có đơn là phải có bản ghi thanh toán + vận chuyển theo dõi.
        create_payment_for_order(order, method=payment_method)
        create_shipping_for_order(order, shipping_fee=shipping_fee)

        # Xóa các item đã đặt khỏi giỏ (chỉ những item được chọn, không đụng phần chưa chọn)
        cart.items.filter(id__in=[i.id for i in selected_items]).delete()

    return order


def cancel_order(user, order_id, reason=""):
    """
    Khách tự hủy đơn (chỉ khi đơn còn ở trạng thái CHO PHÉP hủy) — hoàn kho
    lại qua release_stock(), đổi status thành CANCELLED.
    """
    from apps.inventory.services import release_stock  # import trễ để tránh vòng lặp import

    order = Order.objects.select_related("customer").get(id=order_id, customer=user)
    if order.status not in CANCELLABLE_STATUSES:
        raise OrderNotCancellableError(
            f"Đơn hàng ở trạng thái '{order.status}' không thể hủy."
        )

    with transaction.atomic():
        for item in order.items.select_related("product"):
            release_stock(
                item.product.id,
                item.quantity,
                reference_id=order.order_code,
                user=user,
                note=f"Hoàn kho do hủy đơn {order.order_code}. Lý do: {reason}",
            )
        order.status = OrderStatus.CANCELLED
        order.note = f"{order.note} | Hủy: {reason}".strip(" |")
        order.save(update_fields=["status", "note", "updated_at"])

    return order


class OrderNotConfirmableError(Exception):
    pass


def confirm_order(staff_user, order_id):
    """STAFF xác nhận đơn (PENDING → CONFIRMED) — bước đầu tiên trong luồng xử lý đơn nội bộ."""
    order = Order.objects.get(id=order_id)
    if order.status != OrderStatus.PENDING:
        raise OrderNotConfirmableError(f"Đơn đang ở trạng thái '{order.status}', không thể xác nhận.")
    order.status = OrderStatus.CONFIRMED
    order.save(update_fields=["status", "updated_at"])
    return order
