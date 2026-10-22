"""Test cho Shipping — state machine + đồng bộ Order/Payment khi DELIVERED."""
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Address, Role, User
from apps.cart import services as cart_services
from apps.orders import services as order_services
from apps.orders.models import OrderStatus
from apps.payments.models import PaymentStatus
from apps.products.models import Category, Product, ProductStatus
from apps.shipping.models import ShippingStatus
from apps.shipping.services import InvalidShippingTransitionError, update_shipping_status

pytestmark = pytest.mark.django_db


@pytest.fixture
def customer():
    return User.objects.create_user(email="cus@test.com", password="Pass12345", full_name="Nguyen Van A")


@pytest.fixture
def staff():
    return User.objects.create_user(email="staff@test.com", password="StaffPass123", role=Role.STAFF)


@pytest.fixture
def address(customer):
    return Address.objects.create(
        user=customer, full_name="Nguyen Van A", phone="0912345678",
        province="Hà Nội", district="Cầu Giấy", ward="Dịch Vọng", detail="Số 1", is_default=True,
    )


@pytest.fixture
def order(customer, address):
    category = Category.objects.create(name="Rau củ")
    product = Product.objects.create(
        category=category, sku="SKU001", name="Cà rốt", price=Decimal("10000"),
        unit="kg", status=ProductStatus.ACTIVE,
    )
    product.inventory.quantity = 10
    product.inventory.save()
    cart_services.add_item(customer, product.id, 2)
    return order_services.checkout(customer, address.id)


class TestOrderAutoCreatesPaymentAndShipping:
    def test_checkout_creates_payment_pending(self, order):
        assert order.payment.status == PaymentStatus.PENDING
        assert order.payment.amount == order.final_amount

    def test_checkout_creates_shipping_waiting_pickup(self, order):
        assert order.shipping.status == ShippingStatus.WAITING_PICKUP
        assert order.shipping.tracking_code.startswith("SHIP-")


class TestShippingStateMachine:
    def test_valid_transition_succeeds(self, order):
        shipping = update_shipping_status(order.shipping.id, ShippingStatus.PICKED_UP)
        assert shipping.status == ShippingStatus.PICKED_UP
        assert shipping.picked_up_at is not None

    def test_invalid_transition_raises(self, order):
        """Không cho nhảy cóc từ WAITING_PICKUP thẳng lên DELIVERED."""
        with pytest.raises(InvalidShippingTransitionError):
            update_shipping_status(order.shipping.id, ShippingStatus.DELIVERED)

    def test_cannot_transition_from_terminal_state(self, order):
        update_shipping_status(order.shipping.id, ShippingStatus.PICKED_UP)
        update_shipping_status(order.shipping.id, ShippingStatus.IN_TRANSIT)
        update_shipping_status(order.shipping.id, ShippingStatus.OUT_FOR_DELIVERY)
        update_shipping_status(order.shipping.id, ShippingStatus.DELIVERED)

        with pytest.raises(InvalidShippingTransitionError):
            update_shipping_status(order.shipping.id, ShippingStatus.IN_TRANSIT)

    def test_delivered_syncs_order_status_and_cod_payment(self, order):
        """
        Bài toán cốt lõi Phase 5: giao hàng thành công (COD) phải tự động
        đổi Order.status = DELIVERED và Payment.status = SUCCESS.
        """
        update_shipping_status(order.shipping.id, ShippingStatus.PICKED_UP)
        update_shipping_status(order.shipping.id, ShippingStatus.IN_TRANSIT)
        update_shipping_status(order.shipping.id, ShippingStatus.OUT_FOR_DELIVERY)
        update_shipping_status(order.shipping.id, ShippingStatus.DELIVERED)

        order.refresh_from_db()
        assert order.status == OrderStatus.DELIVERED
        assert order.payment.status == PaymentStatus.SUCCESS
        assert order.payment.transaction_id.startswith("COD-")

    def test_failed_delivery_allows_retry(self, order):
        update_shipping_status(order.shipping.id, ShippingStatus.PICKED_UP)
        update_shipping_status(order.shipping.id, ShippingStatus.IN_TRANSIT)
        update_shipping_status(order.shipping.id, ShippingStatus.OUT_FOR_DELIVERY)
        update_shipping_status(order.shipping.id, ShippingStatus.FAILED)

        shipping = update_shipping_status(order.shipping.id, ShippingStatus.OUT_FOR_DELIVERY)  # giao lại
        assert shipping.status == ShippingStatus.OUT_FOR_DELIVERY

        order.refresh_from_db()
        assert order.status != OrderStatus.DELIVERED  # chưa giao thành công thì Order chưa đổi


class TestShippingAPI:
    def test_customer_cannot_access_shipping_list(self, order, customer):
        client = APIClient()
        client.force_authenticate(customer)
        response = client.get(reverse("shipping:shipping-list"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_staff_can_update_shipping_status(self, order, staff):
        client = APIClient()
        client.force_authenticate(staff)
        response = client.post(
            reverse("shipping:update-status", kwargs={"shipping_id": order.shipping.id}),
            {"status": "PICKED_UP"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "PICKED_UP"

    def test_staff_invalid_transition_returns_400_not_500(self, order, staff):
        client = APIClient()
        client.force_authenticate(staff)
        response = client.post(
            reverse("shipping:update-status", kwargs={"shipping_id": order.shipping.id}),
            {"status": "DELIVERED"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
