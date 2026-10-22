"""Test cho RefundRequest — điều kiện được hoàn tiền, luồng approve/reject/complete."""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Address, Role, User
from apps.cart import services as cart_services
from apps.orders import services as order_services
from apps.orders.models import OrderStatus
from apps.products.models import Category, Product, ProductStatus
from apps.refunds import services as refund_services
from apps.refunds.models import RefundStatus
from apps.shipping.services import update_shipping_status

pytestmark = pytest.mark.django_db


@pytest.fixture
def customer():
    return User.objects.create_user(email="cus@test.com", password="Pass12345")


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
def delivered_order(customer, address):
    category = Category.objects.create(name="Rau củ")
    product = Product.objects.create(
        category=category, sku="SKU001", name="Cà rốt", price=Decimal("10000"),
        unit="kg", status=ProductStatus.ACTIVE,
    )
    product.inventory.quantity = 10
    product.inventory.save()
    cart_services.add_item(customer, product.id, 2)
    order = order_services.checkout(customer, address.id)

    for s in ["PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED"]:
        update_shipping_status(order.shipping.id, s)
    order.refresh_from_db()
    return order


class TestRequestRefund:
    def test_can_request_refund_for_delivered_order(self, customer, delivered_order):
        refund = refund_services.request_refund(
            customer, delivered_order.id, reason="Sản phẩm bị hư hỏng", amount=Decimal("20000")
        )
        assert refund.status == RefundStatus.REQUESTED

    def test_cannot_request_refund_for_pending_order(self, customer, address):
        category = Category.objects.create(name="Rau củ")
        product = Product.objects.create(
            category=category, sku="SKU002", name="Khoai lang", price=Decimal("10000"),
            unit="kg", status=ProductStatus.ACTIVE,
        )
        product.inventory.quantity = 5
        product.inventory.save()
        cart_services.add_item(customer, product.id, 1)
        pending_order = order_services.checkout(customer, address.id)

        with pytest.raises(ValidationError):
            refund_services.request_refund(customer, pending_order.id, reason="Đổi ý", amount=Decimal("10000"))

    def test_cannot_request_refund_amount_exceeding_order(self, customer, delivered_order):
        with pytest.raises(ValidationError):
            refund_services.request_refund(
                customer, delivered_order.id, reason="Test", amount=Decimal("999999")
            )


class TestRefundWorkflow:
    def test_approve_then_complete_updates_order_status(self, customer, staff, delivered_order):
        refund = refund_services.request_refund(
            customer, delivered_order.id, reason="Hư hỏng", amount=Decimal("20000")
        )
        refund_services.approve_refund(refund.id, staff, note="Đã kiểm tra, đồng ý hoàn")
        completed = refund_services.complete_refund(refund.id, staff, note="Đã chuyển khoản")

        assert completed.status == RefundStatus.COMPLETED
        delivered_order.refresh_from_db()
        assert delivered_order.status == OrderStatus.REFUNDED

    def test_reject_refund(self, customer, staff, delivered_order):
        refund = refund_services.request_refund(
            customer, delivered_order.id, reason="Đổi ý", amount=Decimal("20000")
        )
        rejected = refund_services.reject_refund(refund.id, staff, note="Không đủ điều kiện")
        assert rejected.status == RefundStatus.REJECTED

    def test_cannot_approve_twice(self, customer, staff, delivered_order):
        refund = refund_services.request_refund(
            customer, delivered_order.id, reason="Test", amount=Decimal("10000")
        )
        refund_services.approve_refund(refund.id, staff)
        with pytest.raises(ValidationError):
            refund_services.approve_refund(refund.id, staff)

    def test_cannot_complete_before_approve(self, customer, staff, delivered_order):
        refund = refund_services.request_refund(
            customer, delivered_order.id, reason="Test", amount=Decimal("10000")
        )
        with pytest.raises(ValidationError):
            refund_services.complete_refund(refund.id, staff)


class TestRefundAPI:
    def test_customer_can_create_and_view_own_refund(self, customer, delivered_order):
        client = APIClient()
        client.force_authenticate(customer)
        response = client.post(
            reverse("refunds:create-refund"),
            {"order_id": delivered_order.id, "reason": "Hư hỏng", "amount": "20000"},
        )
        assert response.status_code == status.HTTP_201_CREATED

        list_resp = client.get(reverse("refunds:my-refund-list"))
        assert list_resp.data["count"] == 1

    def test_customer_cannot_access_staff_refund_list(self, customer):
        client = APIClient()
        client.force_authenticate(customer)
        response = client.get(reverse("refunds:staff-refund-list"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_staff_can_approve_via_api(self, customer, staff, delivered_order):
        client = APIClient()
        client.force_authenticate(customer)
        create_resp = client.post(
            reverse("refunds:create-refund"),
            {"order_id": delivered_order.id, "reason": "Hư hỏng", "amount": "20000"},
        )
        refund_id = create_resp.data["id"]

        staff_client = APIClient()
        staff_client.force_authenticate(staff)
        approve_resp = staff_client.post(
            reverse("refunds:approve-refund", kwargs={"refund_id": refund_id}), {"note": "OK"}
        )
        assert approve_resp.status_code == status.HTTP_200_OK
        assert approve_resp.data["status"] == "APPROVED"
