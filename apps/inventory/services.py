"""
Service layer cho Inventory — nơi DUY NHẤT được phép thay đổi Inventory.quantity.

Bài toán cốt lõi: 100 người cùng mua 1 sản phẩm chỉ còn 1 đơn vị tồn kho.
Giải pháp: Pessimistic Locking bằng select_for_update() bên trong
transaction.atomic(). Khi request đầu tiên vào, DB khóa row Inventory
của sản phẩm đó (row-level lock). 99 request còn lại phải ĐỢI cho đến khi
transaction đầu commit hoặc rollback — không đọc được giá trị "cũ".
Nhờ vậy quantity không thể bị âm và không có 2 người cùng mua được
đơn vị cuối cùng.

Lưu ý production: select_for_update() cần backend hỗ trợ row-level lock
thật (PostgreSQL, MySQL InnoDB, SQL Server qua mssql-django) — đây chính
là DB thật project đang dùng (SQL Server). SQLite (chỉ dùng khi chạy
`pytest` cục bộ) KHÔNG hỗ trợ row-lock thật nên test liên quan race
condition ở app này mang tính minh họa logic, không thay thế được việc
test tải thực tế trên SQL Server / staging.
"""
from django.db import transaction

from apps.inventory.models import Inventory, InventoryTransaction, ReferenceType, TransactionType


class InsufficientStockError(Exception):
    """Ném ra khi không đủ tồn kho để xuất/trừ."""

    def __init__(self, product_id, requested, available):
        self.product_id = product_id
        self.requested = requested
        self.available = available
        super().__init__(
            f"Sản phẩm không đủ số lượng trong kho (yêu cầu {requested}, còn {available})."
        )


def reserve_stock(
    product_id, quantity, *, reference_type=ReferenceType.ORDER, reference_id="", user=None, note=""
):
    """
    Trừ tồn kho khi khách đặt hàng (checkout). Đây là hàm giải quyết trực tiếp
    bài toán "100 người mua 1 sản phẩm cuối".

    - Mở transaction.atomic() để toàn bộ thao tác (đọc + kiểm tra + trừ +
      ghi log) là 1 đơn vị nguyên tử — không có race condition ở giữa.
    - select_for_update() khóa row Inventory của product_id này. Request
      khác gọi cùng hàm với cùng product_id sẽ BỊ CHẶN (chờ) tại chính
      dòng .select_for_update() cho đến khi transaction này commit/rollback.
    - Sau khi có lock, kiểm tra đủ hàng chưa — nếu không đủ, raise ngay,
      transaction rollback tự động (không trừ kho).
    """
    with transaction.atomic():
        inventory = Inventory.objects.select_for_update().select_related("product").get(
            product_id=product_id
        )

        if inventory.quantity < quantity:
            raise InsufficientStockError(product_id, quantity, inventory.quantity)

        inventory.quantity -= quantity
        inventory.save(update_fields=["quantity", "updated_at"])

        InventoryTransaction.objects.create(
            inventory=inventory,
            transaction_type=TransactionType.OUT,
            quantity=quantity,
            reference_type=reference_type,
            reference_id=str(reference_id),
            created_by=user,
            note=note,
        )
    return inventory


def release_stock(
    product_id, quantity, *, reference_type=ReferenceType.RETURN, reference_id="", user=None, note=""
):
    """Hoàn tồn kho khi đơn bị hủy/hoàn hàng — cộng ngược lại số đã trừ."""
    with transaction.atomic():
        inventory = Inventory.objects.select_for_update().get(product_id=product_id)
        inventory.quantity += quantity
        inventory.save(update_fields=["quantity", "updated_at"])

        InventoryTransaction.objects.create(
            inventory=inventory,
            transaction_type=TransactionType.IN,
            quantity=quantity,
            reference_type=reference_type,
            reference_id=str(reference_id),
            created_by=user,
            note=note or "Hoàn kho do hủy/hoàn đơn.",
        )
    return inventory


def receive_stock(
    product_id, quantity, *, reference_type=ReferenceType.PURCHASE_ORDER, reference_id="", user=None, note=""
):
    """STAFF nhập kho — cộng thêm tồn kho (ví dụ khi nhận hàng từ nhà cung cấp)."""
    if quantity <= 0:
        raise ValueError("Số lượng nhập kho phải lớn hơn 0.")

    with transaction.atomic():
        inventory = Inventory.objects.select_for_update().get(product_id=product_id)
        inventory.quantity += quantity
        inventory.save(update_fields=["quantity", "updated_at"])

        InventoryTransaction.objects.create(
            inventory=inventory,
            transaction_type=TransactionType.IN,
            quantity=quantity,
            reference_type=reference_type,
            reference_id=str(reference_id),
            created_by=user,
            note=note,
        )
    return inventory


def adjust_stock(product_id, new_quantity, *, user=None, note=""):
    """
    STAFF điều chỉnh tồn kho sau kiểm kê thực tế — set thẳng về new_quantity
    (khác receive/reserve là cộng/trừ tương đối). Vẫn ghi lại chênh lệch
    (delta) vào InventoryTransaction để không mất lịch sử.
    """
    if new_quantity < 0:
        raise ValueError("Tồn kho sau điều chỉnh không được âm.")

    with transaction.atomic():
        inventory = Inventory.objects.select_for_update().get(product_id=product_id)
        delta = new_quantity - inventory.quantity
        inventory.quantity = new_quantity
        inventory.save(update_fields=["quantity", "updated_at"])

        InventoryTransaction.objects.create(
            inventory=inventory,
            transaction_type=TransactionType.ADJUST,
            quantity=delta,
            reference_type=ReferenceType.MANUAL,
            created_by=user,
            note=note or f"Điều chỉnh kiểm kê (chênh lệch {delta:+d}).",
        )
    return inventory
