"""
Test cho Checkout — apps/orders. Trọng tâm: trừ kho đúng, snapshot giá/địa
chỉ bất biến, rollback toàn bộ khi 1 sản phẩm trong đơn hết hàng.
Chạy: pytest apps/orders/tests/test_checkout.py -v
"""
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Address, User
from apps.cart import services as cart_services
from apps.orders import services as order_services
from apps.orders.models import Order, OrderStatus
from apps.orders.services import EmptyCartError
from apps.products.models import Category, Product, ProductStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def customer():
    return User.objects.create_user(email="cus@test.com", password="Pass12345", full_name="Nguyen Van A")


@pytest.fixture
def address(customer):
    return Address.objects.create(
        user=customer, full_name="Nguyen Van A", phone="0912345678",
        province="Hà Nội", district="Cầu Giấy", ward="Dịch Vọng", detail="Số 1, ngõ 2", is_default=True,
    )


def make_product(name="Cà rốt", sku="SKU001", price="10000", stock=10):
    category, _ = Category.objects.get_or_create(name="Rau củ")
    p = Product.objects.create(
        category=category, sku=sku, name=name, price=Decimal(price),
        unit="kg", status=ProductStatus.ACTIVE,
    )
    p.inventory.quantity = stock
    p.inventory.save()
    return p


@pytest.fixture
def product():
    return make_product()


class TestCheckoutSuccess:
    def test_checkout_creates_order_and_reduces_stock(self, customer, address, product):
        cart_services.add_item(customer, product.id, 3)

        order = order_services.checkout(customer, address.id)

        assert order.status == OrderStatus.PENDING
        assert order.items.count() == 1
        assert order.items.first().quantity == 3
        assert order.total_amount == Decimal("30000")

        product.inventory.refresh_from_db()
        assert product.inventory.quantity == 7  # 10 - 3

    def test_checkout_clears_purchased_items_from_cart(self, customer, address, product):
        cart_services.add_item(customer, product.id, 2)
        order_services.checkout(customer, address.id)

        from apps.cart.models import Cart
        cart = Cart.objects.get(user=customer)
        assert cart.items.count() == 0

    def test_checkout_only_includes_selected_items(self, customer, address, product):
        p2 = make_product(name="Khoai lang", sku="SKU002")
        item1 = cart_services.add_item(customer, product.id, 1)
        cart_services.add_item(customer, p2.id, 1)
        cart_services.toggle_selected(customer, item1.id, False)  # bỏ chọn sản phẩm 1

        order = order_services.checkout(customer, address.id)

        assert order.items.count() == 1
        assert order.items.first().product_name_snapshot == "Khoai lang"
        product.inventory.refresh_from_db()
        assert product.inventory.quantity == 10  # không bị trừ vì không được chọn

    def test_checkout_with_empty_cart_raises(self, customer, address):
        with pytest.raises(EmptyCartError):
            order_services.checkout(customer, address.id)


class TestCheckoutRollback:
    def test_checkout_rolls_back_entirely_when_one_item_out_of_stock(self, customer, address, product):
        """
        Đơn có 2 sản phẩm: sản phẩm 1 đủ hàng, sản phẩm 2 KHÔNG đủ hàng.
        Toàn bộ đơn phải rollback — sản phẩm 1 KHÔNG bị trừ kho, KHÔNG có
        Order nào được tạo (không phải đơn 'nửa vời' thiếu OrderItem).
        """
        p2 = make_product(name="Khoai lang", sku="SKU002", stock=1)
        cart_services.add_item(customer, product.id, 2)  # sản phẩm 1: đủ hàng (còn 10)

        # Thêm sản phẩm 2 vượt tồn kho trực tiếp vào CartItem (bỏ qua validate
        # của add_item) để mô phỏng tình huống tồn kho vừa giảm sau khi khách
        # đã cho vào giỏ — đúng lý do checkout PHẢI kiểm tra lại lần cuối.
        from apps.cart.models import CartItem, Cart
        cart = Cart.objects.get(user=customer)
        CartItem.objects.create(cart=cart, product=p2, quantity=5, selected=True)  # yêu cầu 5, chỉ còn 1

        orders_before = Order.objects.count()

        with pytest.raises(Exception):  # InsufficientStockError từ reserve_stock
            order_services.checkout(customer, address.id)

        assert Order.objects.count() == orders_before  # KHÔNG tạo đơn nào
        product.inventory.refresh_from_db()
        assert product.inventory.quantity == 10  # sản phẩm 1 KHÔNG bị trừ (rollback)
        p2.inventory.refresh_from_db()
        assert p2.inventory.quantity == 1  # sản phẩm 2 vẫn giữ nguyên


class TestSnapshotImmutability:
    def test_price_change_after_order_does_not_affect_order_item(self, customer, address, product):
        cart_services.add_item(customer, product.id, 1)
        order = order_services.checkout(customer, address.id)

        product.price = Decimal("999999")
        product.save()

        order.refresh_from_db()
        assert order.items.first().price_at_purchase == Decimal("10000")  # vẫn giá lúc mua

    def test_address_change_after_order_does_not_affect_order_snapshot(self, customer, address, product):
        cart_services.add_item(customer, product.id, 1)
        order = order_services.checkout(customer, address.id)

        address.detail = "Địa chỉ mới hoàn toàn"
        address.save()

        order.refresh_from_db()
        assert order.shipping_address["detail"] == "Số 1, ngõ 2"  # vẫn địa chỉ lúc đặt


class TestCancelOrder:
    def test_cancel_order_restores_stock(self, customer, address, product):
        cart_services.add_item(customer, product.id, 3)
        order = order_services.checkout(customer, address.id)
        product.inventory.refresh_from_db()
        assert product.inventory.quantity == 7

        cancelled = order_services.cancel_order(customer, order.id, reason="Đổi ý")

        assert cancelled.status == OrderStatus.CANCELLED
        product.inventory.refresh_from_db()
        assert product.inventory.quantity == 10  # hoàn lại đủ

    def test_cannot_cancel_delivered_order(self, customer, address, product):
        cart_services.add_item(customer, product.id, 1)
        order = order_services.checkout(customer, address.id)
        order.status = OrderStatus.DELIVERED
        order.save()

        with pytest.raises(order_services.OrderNotCancellableError):
            order_services.cancel_order(customer, order.id)


class TestCheckoutAPI:
    def test_checkout_via_api(self, customer, address, product):
        client = APIClient()
        client.force_authenticate(customer)
        client.post(reverse("cart:cart-add-item"), {"product_id": product.id, "quantity": 2})

        response = client.post(reverse("orders:checkout"), {"address_id": address.id})

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["total_amount"] == "20000.00"
        assert response.data["shipping_address"]["province"] == "Hà Nội"

    def test_checkout_insufficient_stock_returns_400_not_500(self, customer, address):
        p = make_product(stock=1)
        client = APIClient()
        client.force_authenticate(customer)
        # Thêm vượt tồn kho thẳng vào cart model để bỏ qua validate ở add_item
        from apps.cart.models import Cart, CartItem
        cart, _ = Cart.objects.get_or_create(user=customer)
        CartItem.objects.create(cart=cart, product=p, quantity=5, selected=True)

        response = client.post(reverse("orders:checkout"), {"address_id": address.id})
        assert response.status_code == status.HTTP_400_BAD_REQUEST  # KHÔNG phải lỗi 500

    def test_view_order_list_and_detail(self, customer, address, product):
        client = APIClient()
        client.force_authenticate(customer)
        client.post(reverse("cart:cart-add-item"), {"product_id": product.id, "quantity": 1})
        checkout_resp = client.post(reverse("orders:checkout"), {"address_id": address.id})
        order_code = checkout_resp.data["order_code"]

        list_resp = client.get(reverse("orders:order-list"))
        assert list_resp.data["count"] == 1

        detail_resp = client.get(reverse("orders:order-detail", kwargs={"order_code": order_code}))
        assert detail_resp.data["order_code"] == order_code

    def test_customer_cannot_view_others_order(self, customer, address, product):
        other = User.objects.create_user(email="other@test.com", password="Pass12345")
        client = APIClient()
        client.force_authenticate(customer)
        client.post(reverse("cart:cart-add-item"), {"product_id": product.id, "quantity": 1})
        checkout_resp = client.post(reverse("orders:checkout"), {"address_id": address.id})
        order_code = checkout_resp.data["order_code"]

        other_client = APIClient()
        other_client.force_authenticate(other)
        response = other_client.get(reverse("orders:order-detail", kwargs={"order_code": order_code}))
        assert response.status_code == status.HTTP_404_NOT_FOUND
