"""Test Review — điều kiện đã mua hàng, rating summary, API."""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Address, User
from apps.cart import services as cart_services
from apps.orders import services as order_services
from apps.products.models import Category, Product, ProductStatus
from apps.reviews import services as review_services
from apps.reviews.models import Review
from apps.shipping.services import update_shipping_status

pytestmark = pytest.mark.django_db


@pytest.fixture
def customer():
    return User.objects.create_user(email="cus@test.com", password="Pass12345")


@pytest.fixture
def address(customer):
    return Address.objects.create(
        user=customer, full_name="A", phone="0912345678",
        province="HN", district="CG", ward="DV", detail="1", is_default=True,
    )


@pytest.fixture
def product():
    category = Category.objects.create(name="Rau củ")
    return Product.objects.create(
        category=category, sku="SKU001", name="Cà rốt", price=Decimal("10000"),
        unit="kg", status=ProductStatus.ACTIVE,
    )


def deliver_order_for(customer, address, product, quantity=1):
    product.inventory.quantity = 20
    product.inventory.save()
    cart_services.add_item(customer, product.id, quantity)
    order = order_services.checkout(customer, address.id)
    for s in ["PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED"]:
        update_shipping_status(order.shipping.id, s)
    return order


class TestPurchaseCheck:
    def test_cannot_review_without_purchase(self, customer, product):
        with pytest.raises(ValidationError):
            review_services.create_review(customer, product.id, rating=5)

    def test_cannot_review_when_order_still_pending(self, customer, address, product):
        product.inventory.quantity = 10
        product.inventory.save()
        cart_services.add_item(customer, product.id, 1)
        order_services.checkout(customer, address.id)  # chưa DELIVERED

        with pytest.raises(ValidationError):
            review_services.create_review(customer, product.id, rating=5)

    def test_can_review_after_delivered(self, customer, address, product):
        deliver_order_for(customer, address, product)
        review = review_services.create_review(customer, product.id, rating=5, content="Ngon!")
        assert review.rating == 5

    def test_cannot_review_same_product_twice(self, customer, address, product):
        deliver_order_for(customer, address, product)
        review_services.create_review(customer, product.id, rating=5)
        with pytest.raises(ValidationError):
            review_services.create_review(customer, product.id, rating=3)


class TestRatingSummary:
    def test_summary_with_no_reviews(self, product):
        summary = review_services.get_rating_summary(product.id)
        assert summary["average"] == 0
        assert summary["count"] == 0

    def test_summary_calculates_average_and_distribution(self, customer, address, product):
        deliver_order_for(customer, address, product)
        review_services.create_review(customer, product.id, rating=4)

        other = User.objects.create_user(email="other@test.com", password="Pass12345")
        other_address = Address.objects.create(
            user=other, full_name="B", phone="0987654321",
            province="HN", district="CG", ward="DV", detail="2", is_default=True,
        )
        deliver_order_for(other, other_address, product)
        review_services.create_review(other, product.id, rating=2)

        summary = review_services.get_rating_summary(product.id)
        assert summary["count"] == 2
        assert summary["average"] == 3.0
        assert summary["distribution"][4] == 1
        assert summary["distribution"][2] == 1

    def test_unapproved_review_excluded_from_summary(self, customer, address, product):
        deliver_order_for(customer, address, product)
        review = review_services.create_review(customer, product.id, rating=1)
        review.is_approved = False
        review.save()

        summary = review_services.get_rating_summary(product.id)
        assert summary["count"] == 0


class TestReviewAPI:
    def test_create_review_via_api(self, customer, address, product):
        deliver_order_for(customer, address, product)
        client = APIClient()
        client.force_authenticate(customer)

        response = client.post(
            reverse("reviews:review-create"),
            {"product_id": product.id, "rating": 5, "content": "Rất tốt"},
        )
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_review_without_purchase_returns_400(self, customer, product):
        client = APIClient()
        client.force_authenticate(customer)
        response = client.post(
            reverse("reviews:review-create"), {"product_id": product.id, "rating": 5}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_reviews_public_no_auth_needed(self, customer, address, product):
        deliver_order_for(customer, address, product)
        review_services.create_review(customer, product.id, rating=5)

        client = APIClient()  # không đăng nhập
        response = client.get(reverse("reviews:review-list") + f"?product={product.id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

    def test_update_own_review(self, customer, address, product):
        deliver_order_for(customer, address, product)
        review = review_services.create_review(customer, product.id, rating=3)

        client = APIClient()
        client.force_authenticate(customer)
        response = client.patch(
            reverse("reviews:review-detail", kwargs={"review_id": review.id}), {"rating": 5}
        )
        assert response.data["rating"] == 5

    def test_delete_own_review(self, customer, address, product):
        deliver_order_for(customer, address, product)
        review = review_services.create_review(customer, product.id, rating=3)

        client = APIClient()
        client.force_authenticate(customer)
        response = client.delete(reverse("reviews:review-detail", kwargs={"review_id": review.id}))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Review.objects.filter(id=review.id).exists()
