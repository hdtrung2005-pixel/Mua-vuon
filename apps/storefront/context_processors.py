"""Context processor — inject số lượng giỏ hàng vào mọi template (hiện badge ở nav)."""


def cart_badge(request):
    if not request.user.is_authenticated:
        return {}

    from apps.cart.models import Cart

    cart = Cart.objects.filter(user=request.user).first()
    count = sum(item.quantity for item in cart.items.all()) if cart else 0
    return {"cart_item_count": count}
