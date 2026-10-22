"""
Test cho Phase 3 — Inventory & Concurrency.
Chạy: pytest apps/inventory/tests/test_inventory.py -v
"""
import threading
from decimal import Decimal

import pytest
from django.db import connection
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.inventory.models import Inventory, TransactionType
from apps.inventory.services import (
    InsufficientStockError,
    adjust_stock,
    receive_stock,
    release_stock,
    reserve_stock,
)
from apps.products.models import Category, Product, ProductStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def product():
    category = Category.objects.create(name="Rau củ")
    return Product.objects.create(
        category=category, sku="SKU001", name="Cà rốt", price=Decimal("10000"),
        unit="kg", status=ProductStatus.ACTIVE,
    )


@pytest.fixture
def staff_user():
    return User.objects.create_user(email="staff@test.com", password="StaffPass123", role=Role.STAFF)


class TestInventoryAutoCreated:
    def test_inventory_auto_created_when_product_created(self, product):
        """Signal phải tự tạo Inventory(quantity=0) ngay khi Product được tạo."""
        assert Inventory.objects.filter(product=product).exists()
        assert product.inventory.quantity == 0


class TestReserveStock:
    def test_reserve_stock_success_decreases_quantity(self, product):
        product.inventory.quantity = 10
        product.inventory.save()

        inventory = reserve_stock(product.id, 3, reference_id="ORDER-1")

        assert inventory.quantity == 7
        tx = inventory.transactions.latest("created_at")
        assert tx.transaction_type == TransactionType.OUT
        assert tx.quantity == 3

    def test_reserve_stock_raises_when_insufficient(self, product):
        product.inventory.quantity = 2
        product.inventory.save()

        with pytest.raises(InsufficientStockError):
            reserve_stock(product.id, 5)

        product.inventory.refresh_from_db()
        assert product.inventory.quantity == 2  # KHÔNG bị trừ khi raise (transaction rollback)

    def test_reserve_stock_never_goes_negative(self, product):
        """Bài toán cốt lõi: mua đúng bằng tồn kho cuối cùng phải về 0, không âm."""
        product.inventory.quantity = 1
        product.inventory.save()

        inventory = reserve_stock(product.id, 1)
        assert inventory.quantity == 0

        with pytest.raises(InsufficientStockError):
            reserve_stock(product.id, 1)  # người thứ 2 phải bị chặn ngay
        product.inventory.refresh_from_db()
        assert product.inventory.quantity == 0  # vẫn = 0, không âm


class TestReserveStockConcurrency:
    """
    Mô phỏng '100 người mua 1 sản phẩm cuối' bằng nhiều thread cùng gọi
    reserve_stock() trên CÙNG 1 sản phẩm chỉ còn 1 tồn kho.

    Lưu ý: test này chạy trên SQLite (không có row-level lock thật như
    PostgreSQL/SQL Server), nên chỉ minh họa logic ở mức có thể — kết quả
    đúng tuyệt đối (chỉ 1/10 thread thành công) cần được xác nhận lại khi
    chạy thật trên SQL Server (DB chính thức của project).
    """

    @pytest.mark.django_db(transaction=True)
    def test_only_one_thread_succeeds_when_stock_is_one(self, product):
        product.inventory.quantity = 1
        product.inventory.save()

        results = []
        lock = threading.Lock()

        def try_buy():
            import time

            from django.db.utils import OperationalError

            attempts_left = 5
            while attempts_left > 0:
                try:
                    reserve_stock(product.id, 1)
                    with lock:
                        results.append("success")
                    return
                except InsufficientStockError:
                    with lock:
                        results.append("failed")
                    return
                except OperationalError as exc:
                    # "database is locked" là giới hạn riêng của SQLite (single-writer),
                    # KHÔNG xảy ra trên PostgreSQL/SQL Server thật (có row-level lock
                    # thật qua select_for_update). Thử lại như một client thật sẽ làm,
                    # thay vì để test tự fail vì hạn chế môi trường test.
                    if "locked" not in str(exc).lower() or attempts_left == 1:
                        raise
                    attempts_left -= 1
                    time.sleep(0.05)
                finally:
                    connection.close()

        threads = [threading.Thread(target=try_buy) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results.count("success") == 1
        assert results.count("failed") == 9

        product.inventory.refresh_from_db()
        assert product.inventory.quantity == 0  # tuyệt đối không âm


class TestReleaseAndReceiveStock:
    def test_release_stock_increases_quantity(self, product):
        product.inventory.quantity = 5
        product.inventory.save()

        inventory = release_stock(product.id, 2, reference_id="ORDER-1")
        assert inventory.quantity == 7
        assert inventory.transactions.latest("created_at").transaction_type == TransactionType.IN

    def test_receive_stock_increases_quantity_and_logs(self, product, staff_user):
        inventory = receive_stock(product.id, 20, user=staff_user, note="Nhập từ NCC A")
        assert inventory.quantity == 20
        tx = inventory.transactions.latest("created_at")
        assert tx.created_by == staff_user
        assert tx.note == "Nhập từ NCC A"

    def test_receive_stock_rejects_zero_or_negative(self, product):
        with pytest.raises(ValueError):
            receive_stock(product.id, 0)


class TestAdjustStock:
    def test_adjust_stock_sets_exact_value_and_logs_delta(self, product):
        product.inventory.quantity = 15
        product.inventory.save()

        inventory = adjust_stock(product.id, 10, note="Kiểm kê thực tế")
        assert inventory.quantity == 10
        tx = inventory.transactions.latest("created_at")
        assert tx.transaction_type == TransactionType.ADJUST
        assert tx.quantity == -5  # delta = 10 - 15

    def test_adjust_stock_rejects_negative(self, product):
        with pytest.raises(ValueError):
            adjust_stock(product.id, -1)


class TestInventoryAPI:
    def test_customer_cannot_access_inventory(self, product):
        customer = User.objects.create_user(email="cus@test.com", password="Pass12345")
        client = APIClient()
        client.force_authenticate(customer)

        response = client.get(reverse("inventory:inventory-list"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_staff_can_view_inventory_list(self, product, staff_user):
        client = APIClient()
        client.force_authenticate(staff_user)

        response = client.get(reverse("inventory:inventory-list"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_staff_can_receive_stock_via_api(self, product, staff_user):
        client = APIClient()
        client.force_authenticate(staff_user)

        response = client.post(
            reverse("inventory:receive-stock"),
            {"product_id": product.id, "quantity": 50, "note": "Nhập đầu kỳ"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["quantity"] == 50

    def test_unauthenticated_cannot_receive_stock(self, product):
        client = APIClient()
        response = client.post(
            reverse("inventory:receive-stock"), {"product_id": product.id, "quantity": 10}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
