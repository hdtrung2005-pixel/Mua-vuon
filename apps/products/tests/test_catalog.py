"""
Test cho Phase 2 — Catalog & Caching.
Chạy: pytest apps/products/tests/test_catalog.py -v
"""
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.products.models import Category, Product, ProductImage, ProductStatus
from apps.products.services import get_category_tree, get_active_products_queryset

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_cache():
    """Xóa cache trước mỗi test để test không ảnh hưởng nhau."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def category():
    return Category.objects.create(name="Rau củ")


@pytest.fixture
def product(category):
    p = Product.objects.create(
        category=category,
        sku="SKU001",
        name="Cà rốt Đà Lạt",
        price=Decimal("25000"),
        unit="kg",
        status=ProductStatus.ACTIVE,
    )
    ProductImage.objects.create(product=p, image="products/carrot.jpg", is_primary=True)
    return p


class TestCategoryModel:
    def test_slug_auto_generated(self):
        cat = Category.objects.create(name="Rau ăn lá")
        assert cat.slug == "rau-an-la"

    def test_child_category_relation(self, category):
        child = Category.objects.create(name="Rau ăn lá", parent=category)
        assert child.parent == category
        assert child in category.children.all()


class TestProductModel:
    def test_effective_price_uses_discount_if_present(self, product):
        assert product.effective_price == product.price
        product.discount_price = Decimal("20000")
        product.save()
        assert product.effective_price == Decimal("20000")

    def test_slug_auto_generated_from_name_and_sku(self, product):
        assert "ca-rot" in product.slug and "sku001" in product.slug.lower()

    def test_is_purchasable_only_when_active(self, product):
        assert product.is_purchasable is True
        product.status = ProductStatus.OUT_OF_STOCK
        assert product.is_purchasable is False


class TestNPlusOneQuery:
    """
    Đảm bảo listing sản phẩm không bị N+1 query — đúng yêu cầu
    select_related/prefetch_related đã chốt từ đầu.
    """

    def test_product_list_uses_fixed_number_of_queries_regardless_of_count(self, category):
        for i in range(5):
            p = Product.objects.create(
                category=category, sku=f"SKU{i:03d}", name=f"Sản phẩm {i}",
                price=Decimal("10000"), unit="kg", status=ProductStatus.ACTIVE,
            )
            ProductImage.objects.create(product=p, image=f"products/{i}.jpg", is_primary=True)

        with CaptureQueriesContext(connection) as ctx:
            queryset = get_active_products_queryset()
            for p in queryset:
                _ = p.category.name  # đã select_related, không query thêm
                _ = list(p.images.all())  # đã prefetch_related, không query thêm

        # Kỳ vọng: 1 query cho Product (join category), 1 query cho prefetch images.
        # KHÔNG phải N*2 query như khi thiếu select_related/prefetch_related.
        assert len(ctx.captured_queries) <= 2


class TestCategoryCache:
    def test_category_tree_is_cached_after_first_call(self, category, django_assert_num_queries):
        get_category_tree()  # lần đầu — có query
        with django_assert_num_queries(0):
            get_category_tree()  # lần 2 — phải lấy từ cache, không query DB

    def test_cache_invalidated_when_category_saved(self, category):
        get_category_tree()  # warm cache
        Category.objects.create(name="Danh mục mới")

        result = get_category_tree()
        assert any(c.name == "Danh mục mới" for c in result)


class TestProductAPI:
    def test_list_products(self, api_client, product):
        response = api_client.get(reverse("products:product-list"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["sku"] == "SKU001"

    def test_filter_by_category_slug(self, api_client, product, category):
        url = reverse("products:product-list") + f"?category_slug={category.slug}"
        response = api_client.get(url)
        assert response.data["count"] == 1

        other_cat = Category.objects.create(name="Trái cây")
        url_other = reverse("products:product-list") + f"?category_slug={other_cat.slug}"
        response_other = api_client.get(url_other)
        assert response_other.data["count"] == 0

    def test_filter_by_price_range(self, api_client, product):
        url = reverse("products:product-list") + "?min_price=30000"
        response = api_client.get(url)
        assert response.data["count"] == 0  # sản phẩm giá 25000, không match >= 30000

    def test_search_by_name(self, api_client, product):
        url = reverse("products:product-list") + "?search=Cà rốt"
        response = api_client.get(url)
        assert response.data["count"] == 1

    def test_inactive_product_not_listed(self, api_client, category):
        Product.objects.create(
            category=category, sku="SKU_DRAFT", name="Chưa duyệt",
            price=Decimal("10000"), unit="kg", status=ProductStatus.DRAFT,
        )
        response = api_client.get(reverse("products:product-list"))
        assert response.data["count"] == 0

    def test_product_detail_by_slug(self, api_client, product):
        url = reverse("products:product-detail", kwargs={"slug": product.slug})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["sku"] == "SKU001"
        assert len(response.data["images"]) == 1

    def test_product_detail_404_for_wrong_slug(self, api_client):
        url = reverse("products:product-detail", kwargs={"slug": "khong-ton-tai"})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND
