"""Test recommendation — sản phẩm cùng danh mục + bán chạy nhất (2 tiêu chí đã chốt)."""
from decimal import Decimal

import pytest
from django.core.cache import cache

from apps.accounts.models import Address, User
from apps.cart import services as cart_services
from apps.orders import services as order_services
from apps.products.models import Category, Product, ProductStatus
from apps.products.services import get_best_selling_products, get_related_products
from apps.shipping.services import update_shipping_status

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


def make_product(category, name, sku, stock=20):
    p = Product.objects.create(
        category=category, sku=sku, name=name, price=Decimal("10000"),
        unit="kg", status=ProductStatus.ACTIVE,
    )
    p.inventory.quantity = stock
    p.inventory.save()
    return p


class TestRelatedProducts:
    def test_returns_only_same_category(self):
        cat1 = Category.objects.create(name="Rau củ")
        cat2 = Category.objects.create(name="Trái cây")
        p1 = make_product(cat1, "Cà rốt", "SKU001")
        p2 = make_product(cat1, "Khoai lang", "SKU002")
        make_product(cat2, "Xoài", "SKU003")

        related = list(get_related_products(p1))
        assert p2 in related
        assert all(p.category_id == cat1.id for p in related)

    def test_excludes_itself(self):
        cat = Category.objects.create(name="Rau củ")
        p1 = make_product(cat, "Cà rốt", "SKU001")

        related = list(get_related_products(p1))
        assert p1 not in related


class TestBestSellers:
    def test_best_sellers_ordered_by_total_delivered_quantity(self):
        cat = Category.objects.create(name="Rau củ")
        popular = make_product(cat, "Cà rốt hot", "SKU_HOT")
        unpopular = make_product(cat, "Khoai ít bán", "SKU_COLD")

        customer = User.objects.create_user(email="c@test.com", password="Pass12345")
        address = Address.objects.create(
            user=customer, full_name="A", phone="0912345678",
            province="HN", district="CG", ward="DV", detail="1", is_default=True,
        )

        # Mua "popular" nhiều lần (đơn giao thành công) — mua "unpopular" ít hơn
        for qty in [5, 3]:
            cart_services.add_item(customer, popular.id, qty)
            order = order_services.checkout(customer, address.id)
            for s in ["PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED"]:
                update_shipping_status(order.shipping.id, s)

        cart_services.add_item(customer, unpopular.id, 1)
        order2 = order_services.checkout(customer, address.id)
        for s in ["PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED"]:
            update_shipping_status(order2.shipping.id, s)

        best_sellers = get_best_selling_products()
        assert best_sellers[0].id == popular.id  # bán 8kg > 1kg, phải đứng đầu

    def test_pending_orders_not_counted_as_sold(self):
        """Đơn chưa DELIVERED không được tính vào 'bán chạy'."""
        cat = Category.objects.create(name="Rau củ")
        product = make_product(cat, "Cà rốt", "SKU001")

        customer = User.objects.create_user(email="c2@test.com", password="Pass12345")
        address = Address.objects.create(
            user=customer, full_name="A", phone="0912345678",
            province="HN", district="CG", ward="DV", detail="1", is_default=True,
        )
        cart_services.add_item(customer, product.id, 10)
        order_services.checkout(customer, address.id)  # vẫn PENDING, không giao

        best_sellers = get_best_selling_products()
        assert product not in best_sellers
