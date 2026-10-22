"""Test cho Cart — apps/cart. Chạy: pytest apps/cart/tests/test_cart.py -v"""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.cart import services
from apps.cart.models import Cart
from apps.products.models import Category, Product, ProductStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def customer():
    return User.objects.create_user(email="cus@test.com", password="Pass12345")


@pytest.fixture
def product():
    category = Category.objects.create(name="Rau củ")
    p = Product.objects.create(
        category=category, sku="SKU001", name="Cà rốt", price=Decimal("10000"),
        unit="kg", status=ProductStatus.ACTIVE,
    )
    p.inventory.quantity = 10
    p.inventory.save()
    return p


class TestCartService:
    def test_add_item_creates_cart_automatically(self, customer, product):
        services.add_item(customer, product.id, 2)
        cart = Cart.objects.get(user=customer)
        assert cart.items.count() == 1
        assert cart.items.first().quantity == 2

    def test_add_item_twice_accumulates_quantity(self, customer, product):
        services.add_item(customer, product.id, 2)
        services.add_item(customer, product.id, 3)
        cart = Cart.objects.get(user=customer)
        assert cart.items.count() == 1  # không tạo dòng mới trùng sản phẩm
        assert cart.items.first().quantity == 5

    def test_add_item_rejects_when_exceeds_stock(self, customer, product):
        with pytest.raises(ValidationError):
            services.add_item(customer, product.id, 999)

    def test_update_quantity_rejects_when_exceeds_stock(self, customer, product):
        item = services.add_item(customer, product.id, 2)
        with pytest.raises(ValidationError):
            services.update_item_quantity(customer, item.id, 999)

    def test_cart_total_amount_uses_effective_price(self, customer, product):
        product.discount_price = Decimal("8000")
        product.save()
        services.add_item(customer, product.id, 2)
        cart = Cart.objects.get(user=customer)
        assert cart.total_amount == Decimal("16000")

    def test_unselected_item_excluded_from_total(self, customer, product):
        item = services.add_item(customer, product.id, 2)
        services.toggle_selected(customer, item.id, False)
        cart = Cart.objects.get(user=customer)
        assert cart.total_amount == 0

    def test_remove_item(self, customer, product):
        item = services.add_item(customer, product.id, 2)
        services.remove_item(customer, item.id)
        cart = Cart.objects.get(user=customer)
        assert cart.items.count() == 0


class TestCartAPI:
    def test_add_and_view_cart(self, customer, product):
        client = APIClient()
        client.force_authenticate(customer)

        response = client.post(reverse("cart:cart-add-item"), {"product_id": product.id, "quantity": 3})
        assert response.status_code == status.HTTP_201_CREATED

        detail = client.get(reverse("cart:cart-detail"))
        assert detail.data["items"][0]["quantity"] == 3

    def test_add_item_exceeding_stock_returns_400(self, customer, product):
        client = APIClient()
        client.force_authenticate(customer)
        response = client.post(reverse("cart:cart-add-item"), {"product_id": product.id, "quantity": 999})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_unauthenticated_cannot_access_cart(self, product):
        client = APIClient()
        response = client.get(reverse("cart:cart-detail"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
