"""
Staff Panel — khu vực quản lý nội bộ cho STAFF/ADMIN (SSR, Django Templates).
Tách riêng khỏi storefront (dành cho Customer) và khỏi Django Admin (dành
cho thao tác dữ liệu thô/kỹ thuật) — đây là giao diện vận hành hàng ngày:
xác nhận đơn, cập nhật vận chuyển, theo dõi tồn kho sắp hết.

RBAC: mọi view đều bọc @require_role(Role.ADMIN, Role.STAFF) — Customer
truy cập sẽ bị 403 ngay ở tầng view, không chỉ ẩn link trên giao diện.
"""
from datetime import timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.permissions import require_role
from apps.inventory.models import Inventory
from apps.orders.models import Order, OrderStatus
from apps.orders.services import OrderNotConfirmableError, confirm_order
from apps.shipping.models import ShippingStatus
from apps.shipping.services import InvalidShippingTransitionError, update_shipping_status


@require_role(Role.ADMIN, Role.STAFF)
def dashboard(request):
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

    context = {
        "pending_count": Order.objects.filter(status=OrderStatus.PENDING).count(),
        "confirmed_count": Order.objects.filter(status=OrderStatus.CONFIRMED).count(),
        "low_stock": _low_stock_inventories(),
        "out_of_stock_count": Inventory.objects.filter(quantity=0).count(),
        "today_order_count": Order.objects.filter(created_at__gte=today_start).count(),
        "recent_orders": Order.objects.select_related("customer", "payment", "shipping")
        .order_by("-created_at")[:8],
    }
    return render(request, "staffpanel/dashboard.html", context)


def _low_stock_inventories():
    from django.db.models import F

    return (
        Inventory.objects.select_related("product")
        .filter(quantity__gt=0, quantity__lte=F("low_stock_threshold"))
        .order_by("quantity")[:10]
    )


@require_role(Role.ADMIN, Role.STAFF)
def order_list(request):
    orders = Order.objects.select_related("customer", "payment", "shipping").order_by("-created_at")

    status_filter = request.GET.get("status", "")
    if status_filter:
        orders = orders.filter(status=status_filter)

    paginator = Paginator(orders, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "staffpanel/order_list.html", {
        "page_obj": page_obj,
        "status_filter": status_filter,
        "statuses": OrderStatus.choices,
    })


@require_role(Role.ADMIN, Role.STAFF)
def order_detail(request, order_code):
    order = get_object_or_404(
        Order.objects.select_related("customer", "payment", "shipping").prefetch_related("items"),
        order_code=order_code,
    )

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "confirm":
            try:
                confirm_order(request.user, order.id)
                messages.success(request, "Đã xác nhận đơn hàng.")
            except OrderNotConfirmableError as exc:
                messages.error(request, str(exc))

        elif action == "update_shipping":
            try:
                update_shipping_status(
                    order.shipping.id, request.POST.get("status"), user=request.user,
                    note=request.POST.get("note", ""),
                )
                messages.success(request, "Đã cập nhật trạng thái vận chuyển.")
            except InvalidShippingTransitionError as exc:
                messages.error(request, str(exc))

        return redirect("staffpanel:order-detail", order_code=order.order_code)

    next_shipping_statuses = []
    if hasattr(order, "shipping"):
        from apps.shipping.services import ALLOWED_TRANSITIONS
        next_shipping_statuses = ALLOWED_TRANSITIONS.get(order.shipping.status, set())

    return render(request, "staffpanel/order_detail.html", {
        "order": order,
        "next_shipping_statuses": next_shipping_statuses,
    })


@require_role(Role.ADMIN, Role.STAFF)
def category_list(request):
    from apps.products.models import Category
    from apps.products.services import invalidate_category_cache

    if request.method == "POST":
        action = request.POST.get("action")
        cat_id = request.POST.get("category_id")

        if action == "create":
            Category.objects.create(
                name=request.POST.get("name", "").strip(),
                parent_id=request.POST.get("parent_id") or None,
            )
            messages.success(request, "Đã tạo danh mục mới.")
        elif action == "update":
            cat = get_object_or_404(Category, id=cat_id)
            cat.name = request.POST.get("name", "").strip()
            cat.parent_id = request.POST.get("parent_id") or None
            cat.is_active = request.POST.get("is_active") == "1"
            cat.save()
            messages.success(request, "Đã cập nhật danh mục.")
        elif action == "delete":
            get_object_or_404(Category, id=cat_id).delete()
            messages.success(request, "Đã xóa danh mục.")

        invalidate_category_cache()
        return redirect("staffpanel:category-list")

    categories = Category.objects.select_related("parent").order_by("name")
    return render(request, "staffpanel/category_list.html", {"categories": categories})


@require_role(Role.ADMIN, Role.STAFF)
def product_list(request):
    from apps.products.models import Product

    products = Product.objects.select_related("category", "inventory").order_by("-created_at")

    search = request.GET.get("search", "").strip()
    if search:
        products = products.filter(name__icontains=search)

    paginator = Paginator(products, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "staffpanel/product_list.html", {"page_obj": page_obj, "search": search})


@require_role(Role.ADMIN, Role.STAFF)
def product_form(request, product_id=None):
    """Dùng chung cho tạo mới (product_id=None) và sửa sản phẩm."""
    from apps.products.models import Category, Product, ProductImage, ProductStatus
    from apps.products.services import invalidate_homepage_products_cache

    product = get_object_or_404(Product, id=product_id) if product_id else None
    categories = Category.objects.order_by("name")

    if request.method == "POST":
        data = {
            "category_id": request.POST.get("category_id"),
            "sku": request.POST.get("sku", "").strip(),
            "name": request.POST.get("name", "").strip(),
            "description": request.POST.get("description", "").strip(),
            "price": request.POST.get("price") or 0,
            "discount_price": request.POST.get("discount_price") or None,
            "unit": request.POST.get("unit", "").strip(),
            "origin": request.POST.get("origin", "").strip(),
            "status": request.POST.get("status", ProductStatus.DRAFT),
        }

        if product:
            for field, value in data.items():
                setattr(product, field, value)
            product.save()
            messages.success(request, "Đã cập nhật sản phẩm.")
        else:
            product = Product.objects.create(**data)
            messages.success(request, "Đã tạo sản phẩm mới — tồn kho khởi tạo là 0, vào mục Tồn kho để nhập hàng.")

        if request.FILES.get("image"):
            ProductImage.objects.create(
                product=product, image=request.FILES["image"],
                is_primary=not product.images.exists(),
            )

        invalidate_homepage_products_cache()
        return redirect("staffpanel:product-edit", product_id=product.id)

    return render(request, "staffpanel/product_form.html", {
        "product": product, "categories": categories, "statuses": ProductStatus.choices,
    })


@require_role(Role.ADMIN, Role.STAFF)
def product_image_delete(request, product_id, image_id):
    from apps.products.models import ProductImage

    if request.method == "POST":
        ProductImage.objects.filter(id=image_id, product_id=product_id).delete()
        messages.success(request, "Đã xóa ảnh.")
    return redirect("staffpanel:product-edit", product_id=product_id)


@require_role(Role.ADMIN, Role.STAFF)
def inventory_list(request):
    """Danh sách tồn kho — nhập/điều chỉnh ngay tại đây (thay vì qua Django Admin)."""
    from apps.inventory.services import InsufficientStockError, adjust_stock, receive_stock

    if request.method == "POST":
        action = request.POST.get("action")
        product_id = request.POST.get("product_id")
        note = request.POST.get("note", "").strip()

        try:
            if action == "receive":
                quantity = int(request.POST.get("quantity", 0))
                receive_stock(product_id, quantity, user=request.user, note=note)
                messages.success(request, f"Đã nhập thêm {quantity} vào kho.")
            elif action == "adjust":
                new_quantity = int(request.POST.get("new_quantity", 0))
                adjust_stock(product_id, new_quantity, user=request.user, note=note)
                messages.success(request, f"Đã điều chỉnh tồn kho về {new_quantity}.")
        except ValueError as exc:
            messages.error(request, str(exc))

        return redirect("staffpanel:inventory-list")

    inventories = Inventory.objects.select_related("product", "product__category").order_by("product__name")

    filter_type = request.GET.get("filter", "")
    if filter_type == "low_stock":
        from django.db.models import F
        inventories = inventories.filter(quantity__gt=0, quantity__lte=F("low_stock_threshold"))
    elif filter_type == "out_of_stock":
        inventories = inventories.filter(quantity=0)

    paginator = Paginator(inventories, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "staffpanel/inventory_list.html", {"page_obj": page_obj, "filter_type": filter_type})


@require_role(Role.ADMIN, Role.STAFF)
def inventory_transactions(request, inventory_id):
    """Lịch sử biến động kho của 1 sản phẩm — chỉ xem, không sửa (immutable log, đã chốt từ Phase 3)."""
    from apps.inventory.models import InventoryTransaction

    inventory = get_object_or_404(Inventory.objects.select_related("product"), id=inventory_id)
    transactions = InventoryTransaction.objects.filter(inventory=inventory).select_related("created_by").order_by("-created_at")[:50]

    return render(request, "staffpanel/inventory_transactions.html", {
        "inventory": inventory, "transactions": transactions,
    })


@require_role(Role.ADMIN, Role.STAFF)
def refund_list(request):
    from django.core.exceptions import ValidationError as DjangoValidationError

    from apps.refunds import services as refund_services
    from apps.refunds.models import RefundRequest, RefundStatus

    if request.method == "POST":
        action = request.POST.get("action")
        refund_id = request.POST.get("refund_id")
        note = request.POST.get("note", "").strip()

        try:
            if action == "approve":
                refund_services.approve_refund(refund_id, request.user, note=note)
                messages.success(request, "Đã duyệt yêu cầu hoàn tiền.")
            elif action == "reject":
                refund_services.reject_refund(refund_id, request.user, note=note)
                messages.success(request, "Đã từ chối yêu cầu hoàn tiền.")
            elif action == "complete":
                refund_services.complete_refund(refund_id, request.user, note=note)
                messages.success(request, "Đã đánh dấu hoàn tất hoàn tiền — đơn hàng chuyển sang REFUNDED.")
        except DjangoValidationError as exc:
            messages.error(request, exc.messages[0] if hasattr(exc, "messages") else str(exc))

        return redirect("staffpanel:refund-list")

    refunds = RefundRequest.objects.select_related("order", "order__customer", "processed_by").order_by("-created_at")

    status_filter = request.GET.get("status", "")
    if status_filter:
        refunds = refunds.filter(status=status_filter)

    paginator = Paginator(refunds, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "staffpanel/refund_list.html", {
        "page_obj": page_obj, "status_filter": status_filter, "statuses": RefundStatus.choices,
    })


@require_role(Role.ADMIN)
def revenue_dashboard(request):
    """
    Biểu đồ doanh thu — CHỈ ADMIN được xem (đúng yêu cầu gốc: Warehouse/STAFF
    không được xem doanh thu tổng thể/thông tin tài chính không liên quan).
    Doanh thu tính từ đơn đã DELIVERED (đã thực sự bán được, không tính đơn
    PENDING/CANCELLED để không lệch số liệu).
    """
    import json
    from datetime import timedelta

    from django.db.models import Count, Sum
    from django.db.models.functions import TruncDate

    from apps.products.services import get_best_selling_products

    days = 30
    since = timezone.now() - timedelta(days=days)

    delivered_orders = Order.objects.filter(status=OrderStatus.DELIVERED)

    total_revenue = delivered_orders.aggregate(total=Sum("final_amount"))["total"] or 0

    daily = (
        delivered_orders.filter(updated_at__gte=since)
        .annotate(day=TruncDate("updated_at"))
        .values("day")
        .annotate(revenue=Sum("final_amount"), order_count=Count("id"))
        .order_by("day")
    )
    daily_map = {row["day"].isoformat(): float(row["revenue"]) for row in daily}
    chart_labels = [(since + timedelta(days=i)).date().isoformat() for i in range(days + 1)]
    chart_data = [daily_map.get(label, 0) for label in chart_labels]

    status_counts = list(
        Order.objects.values("status").annotate(count=Count("id")).order_by("-count")
    )

    context = {
        "total_revenue": total_revenue,
        "delivered_count": delivered_orders.count(),
        "chart_labels": json.dumps(chart_labels),
        "chart_data": json.dumps(chart_data),
        "status_labels": json.dumps([OrderStatus(s["status"]).label for s in status_counts]),
        "status_data": json.dumps([s["count"] for s in status_counts]),
        "top_products": get_best_selling_products(limit=5),
    }
    return render(request, "staffpanel/revenue.html", context)
