"""
Storefront — views SSR cho khách hàng (Django Templates + Tailwind, đã chốt).
Gọi trực tiếp service layer (không qua HTTP API) vì đang chạy trong cùng
process Django — nhanh hơn và tránh vòng lặp gọi API của chính mình.
"""
from django.contrib import messages
from django.contrib.auth import login as django_login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import Address, Role, User
from apps.products.services import (
    get_active_products_queryset,
    get_best_selling_products,
    get_category_tree,
    get_related_products,
)
from apps.reviews.models import Review
from apps.reviews.services import get_rating_summary


def home(request):
    context = {
        "categories": get_category_tree(),
        "best_sellers": get_best_selling_products(limit=8),
        "new_arrivals": get_active_products_queryset().order_by("-created_at")[:8],
    }
    return render(request, "storefront/home.html", context)


def product_list(request):
    queryset = get_active_products_queryset()

    search = request.GET.get("search", "").strip()
    if search:
        queryset = queryset.filter(name__icontains=search)

    category_slug = request.GET.get("category", "").strip()
    if category_slug:
        queryset = queryset.filter(category__slug=category_slug)

    sort = request.GET.get("sort", "-created_at")
    allowed_sorts = {"-created_at", "price", "-price", "name"}
    if sort in allowed_sorts:
        queryset = queryset.order_by(sort)

    paginator = Paginator(queryset, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "page_obj": page_obj,
        "categories": get_category_tree(),
        "search": search,
        "category_slug": category_slug,
        "sort": sort,
    }
    return render(request, "storefront/product_list.html", context)


def product_detail(request, slug):
    from apps.reviews import services as review_services

    product = get_object_or_404(get_active_products_queryset(), slug=slug)

    if request.method == "POST" and request.user.is_authenticated:
        form_type = request.POST.get("form", "add_to_cart")

        if form_type == "review":
            rating = int(request.POST.get("rating", 5))
            content = request.POST.get("content", "").strip()
            try:
                existing = Review.objects.filter(product=product, user=request.user).first()
                if existing:
                    review_services.update_review(request.user, existing.id, rating=rating, content=content)
                    messages.success(request, "Đã cập nhật đánh giá của bạn.")
                else:
                    review_services.create_review(request.user, product.id, rating=rating, content=content)
                    messages.success(request, "Cảm ơn bạn đã đánh giá sản phẩm!")
            except ValidationError as exc:
                messages.error(request, exc.messages[0] if hasattr(exc, "messages") else str(exc))
            return redirect("storefront:product-detail", slug=product.slug)

        if form_type == "delete_review":
            review_services.delete_review(request.user, request.POST.get("review_id"))
            messages.success(request, "Đã xóa đánh giá của bạn.")
            return redirect("storefront:product-detail", slug=product.slug)

        if form_type == "toggle_wishlist":
            from apps.products.services import toggle_wishlist

            added = toggle_wishlist(request.user, product.id)
            messages.success(request, "Đã thêm vào yêu thích." if added else "Đã bỏ khỏi yêu thích.")
            return redirect("storefront:product-detail", slug=product.slug)

        from apps.cart import services as cart_services

        quantity = int(request.POST.get("quantity", 1))
        try:
            cart_services.add_item(request.user, product.id, quantity)
            messages.success(request, f"Đã thêm {quantity} {product.unit} \"{product.name}\" vào giỏ hàng.")
            return redirect("storefront:cart")
        except ValidationError as exc:
            messages.error(request, exc.messages[0] if hasattr(exc, "messages") else str(exc))

    my_review = None
    has_purchased = False
    is_wishlisted = False
    if request.user.is_authenticated:
        my_review = Review.objects.filter(product=product, user=request.user).first()
        has_purchased = review_services.has_purchased_product(request.user, product.id)
        from apps.products.models import Wishlist
        is_wishlisted = Wishlist.objects.filter(user=request.user, product=product).exists()

    context = {
        "product": product,
        "rating_summary": get_rating_summary(product.id),
        "related_products": get_related_products(product),
        "reviews": Review.objects.filter(product=product, is_approved=True).exclude(
            user=request.user if request.user.is_authenticated else None
        ).select_related("user")[:10],
        "my_review": my_review,
        "has_purchased": has_purchased,
        "is_wishlisted": is_wishlisted,
    }
    return render(request, "storefront/product_detail.html", context)


@login_required(login_url="accounts:login")
def wishlist(request):
    from apps.products.services import get_wishlist_products

    products = get_wishlist_products(request.user)
    return render(request, "storefront/wishlist.html", {"products": products})


def register(request):
    """Đăng ký tài khoản CUSTOMER qua web (khác /api/v1/auth/register/ — cùng logic, khác giao diện)."""
    if request.user.is_authenticated:
        return redirect("storefront:home")

    errors = {}
    form_data = {}

    if request.method == "POST":
        form_data = {
            "email": request.POST.get("email", "").strip(),
            "full_name": request.POST.get("full_name", "").strip(),
            "phone": request.POST.get("phone", "").strip(),
        }
        password = request.POST.get("password", "")
        password_confirm = request.POST.get("password_confirm", "")

        if not form_data["email"]:
            errors["email"] = "Vui lòng nhập email."
        elif User.objects.filter(email=form_data["email"]).exists():
            errors["email"] = "Email này đã được đăng ký."
        if len(password) < 8:
            errors["password"] = "Mật khẩu phải có ít nhất 8 ký tự."
        if password != password_confirm:
            errors["password_confirm"] = "Mật khẩu xác nhận không khớp."

        if not errors:
            user = User.objects.create_user(
                email=form_data["email"],
                password=password,
                full_name=form_data["full_name"],
                phone=form_data["phone"],
                role=Role.CUSTOMER,
            )
            django_login(request, user)
            messages.success(request, "Đăng ký thành công — chào mừng bạn đến với Mùa Vườn!")
            return redirect("storefront:home")

    return render(request, "storefront/register.html", {"errors": errors, "form_data": form_data})


@login_required(login_url="accounts:login")
def cart(request):
    from apps.cart import services as cart_services

    cart_obj = cart_services.get_or_create_cart(request.user)

    if request.method == "POST":
        action = request.POST.get("action")
        item_id = request.POST.get("item_id")
        try:
            if action == "update":
                cart_services.update_item_quantity(request.user, item_id, int(request.POST.get("quantity", 1)))
            elif action == "remove":
                cart_services.remove_item(request.user, item_id)
                messages.success(request, "Đã xóa sản phẩm khỏi giỏ hàng.")
            elif action == "toggle":
                cart_services.toggle_selected(request.user, item_id, request.POST.get("selected") == "1")
        except ValidationError as exc:
            messages.error(request, exc.messages[0] if hasattr(exc, "messages") else str(exc))
        return redirect("storefront:cart")

    return render(request, "storefront/cart.html", {"cart": cart_obj})


@login_required(login_url="accounts:login")
def checkout(request):
    from apps.orders import services as order_services
    from apps.orders.services import EmptyCartError
    from apps.inventory.services import InsufficientStockError

    addresses = Address.objects.filter(user=request.user)

    if request.method == "POST":
        if request.POST.get("form") == "new_address":
            address = Address.objects.create(
                user=request.user,
                full_name=request.POST.get("full_name", "").strip(),
                phone=request.POST.get("phone", "").strip(),
                province=request.POST.get("province", "").strip(),
                district=request.POST.get("district", "").strip(),
                ward=request.POST.get("ward", "").strip(),
                detail=request.POST.get("detail", "").strip(),
                note=request.POST.get("note", "").strip(),
                is_default=not addresses.exists(),
            )
            messages.success(request, "Đã thêm địa chỉ mới.")
            return redirect("storefront:checkout")

        address_id = request.POST.get("address_id")
        payment_method = request.POST.get("payment_method", "COD")
        note = request.POST.get("note", "").strip()

        try:
            order = order_services.checkout(
                user=request.user, address_id=address_id, payment_method=payment_method, note=note
            )
            messages.success(request, f"Đặt hàng thành công! Mã đơn: {order.order_code}")
            return redirect("storefront:order-detail", order_code=order.order_code)
        except EmptyCartError as exc:
            messages.error(request, str(exc))
        except InsufficientStockError:
            messages.error(request, "Có sản phẩm trong giỏ không đủ số lượng trong kho — vui lòng kiểm tra lại giỏ hàng.")
        except (ValidationError, Address.DoesNotExist) as exc:
            messages.error(request, "Không thể đặt hàng — kiểm tra lại địa chỉ giao hàng.")
        return redirect("storefront:checkout")

    from apps.cart import services as cart_services
    cart_obj = cart_services.get_or_create_cart(request.user)

    return render(request, "storefront/checkout.html", {"cart": cart_obj, "addresses": addresses})


@login_required(login_url="accounts:login")
def order_list(request):
    from apps.orders.models import Order

    orders = (
        Order.objects.filter(customer=request.user)
        .select_related("payment", "shipping")
        .prefetch_related("items")
        .order_by("-created_at")
    )
    return render(request, "storefront/order_list.html", {"orders": orders})


@login_required(login_url="accounts:login")
def order_detail(request, order_code):
    from apps.orders.models import Order
    from apps.refunds.models import RefundRequest

    order = get_object_or_404(
        Order.objects.select_related("payment", "shipping").prefetch_related("items"),
        order_code=order_code, customer=request.user,
    )

    if request.method == "POST" and request.POST.get("action") == "cancel":
        from apps.orders import services as order_services
        from apps.orders.services import OrderNotCancellableError

        try:
            order_services.cancel_order(request.user, order.id, reason=request.POST.get("reason", ""))
            messages.success(request, "Đã hủy đơn hàng và hoàn lại tồn kho.")
        except OrderNotCancellableError as exc:
            messages.error(request, str(exc))
        return redirect("storefront:order-detail", order_code=order.order_code)

    if request.method == "POST" and request.POST.get("action") == "request_refund":
        from decimal import Decimal, InvalidOperation

        from apps.refunds import services as refund_services

        try:
            amount_raw = request.POST.get("amount")
            amount = Decimal(amount_raw) if amount_raw else order.final_amount
            refund_services.request_refund(
                request.user, order.id,
                reason=request.POST.get("reason", "").strip(),
                amount=amount,
            )
            messages.success(request, "Đã gửi yêu cầu hoàn tiền — chúng tôi sẽ xem xét sớm.")
        except InvalidOperation:
            messages.error(request, "Số tiền không hợp lệ.")
        except ValidationError as exc:
            messages.error(request, exc.messages[0] if hasattr(exc, "messages") else str(exc))
        return redirect("storefront:order-detail", order_code=order.order_code)

    refund_request = RefundRequest.objects.filter(order=order).order_by("-created_at").first()
    can_request_refund = (
        order.status in ("DELIVERED", "CANCELLED") and refund_request is None
    )

    return render(request, "storefront/order_detail.html", {
        "order": order, "refund_request": refund_request, "can_request_refund": can_request_refund,
    })


@login_required(login_url="accounts:login")
def address_list(request):
    """Quản lý địa chỉ — thêm/sửa/xóa/đặt mặc định. Tách riêng khỏi checkout để dùng lại được."""
    if request.method == "POST":
        action = request.POST.get("action")
        address_id = request.POST.get("address_id")

        if action == "create":
            Address.objects.create(
                user=request.user,
                full_name=request.POST.get("full_name", "").strip(),
                phone=request.POST.get("phone", "").strip(),
                province=request.POST.get("province", "").strip(),
                district=request.POST.get("district", "").strip(),
                ward=request.POST.get("ward", "").strip(),
                detail=request.POST.get("detail", "").strip(),
                note=request.POST.get("note", "").strip(),
                is_default=not Address.objects.filter(user=request.user).exists(),
            )
            messages.success(request, "Đã thêm địa chỉ mới.")
        elif action == "update":
            address = get_object_or_404(Address, id=address_id, user=request.user)
            address.full_name = request.POST.get("full_name", "").strip()
            address.phone = request.POST.get("phone", "").strip()
            address.province = request.POST.get("province", "").strip()
            address.district = request.POST.get("district", "").strip()
            address.ward = request.POST.get("ward", "").strip()
            address.detail = request.POST.get("detail", "").strip()
            address.note = request.POST.get("note", "").strip()
            address.save()
            messages.success(request, "Đã cập nhật địa chỉ.")
        elif action == "delete":
            Address.objects.filter(id=address_id, user=request.user).delete()
            messages.success(request, "Đã xóa địa chỉ.")
        elif action == "set_default":
            address = get_object_or_404(Address, id=address_id, user=request.user)
            address.is_default = True
            address.save()  # logic tự tắt is_default của địa chỉ khác đã có sẵn trong Address.save()
            messages.success(request, "Đã đặt làm địa chỉ mặc định.")

        return redirect("storefront:address-list")

    addresses = Address.objects.filter(user=request.user)
    return render(request, "storefront/address_list.html", {"addresses": addresses})
