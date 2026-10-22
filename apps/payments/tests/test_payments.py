"""Test cho Payment services."""
from decimal import Decimal

import pytest

from apps.accounts.models import Address, User
from apps.cart import services as cart_services
from apps.orders import services as order_services
from apps.payments.models import PaymentStatus
from apps.payments.services import mark_payment_failed, mark_payment_success
from apps.products.models import Category, Product, ProductStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def order():
    customer = User.objects.create_user(email="cus@test.com", password="Pass12345")
    address = Address.objects.create(
        user=customer, full_name="A", phone="0912345678",
        province="HN", district="CG", ward="DV", detail="1", is_default=True,
    )
    category = Category.objects.create(name="Rau củ")
    product = Product.objects.create(
        category=category, sku="SKU001", name="Cà rốt", price=Decimal("10000"),
        unit="kg", status=ProductStatus.ACTIVE,
    )
    product.inventory.quantity = 10
    product.inventory.save()
    cart_services.add_item(customer, product.id, 2)
    return order_services.checkout(customer, address.id)


class TestPaymentServices:
    def test_mark_payment_success_sets_timestamp(self, order):
        payment = mark_payment_success(order.id, transaction_id="TX123")
        assert payment.status == PaymentStatus.SUCCESS
        assert payment.transaction_id == "TX123"
        assert payment.paid_at is not None

    def test_mark_payment_failed(self, order):
        payment = mark_payment_failed(order.id, reason="Khách từ chối nhận hàng")
        assert payment.status == PaymentStatus.FAILED
