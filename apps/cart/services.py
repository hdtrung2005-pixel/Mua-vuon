"""Service layer cho giỏ hàng — mọi thao tác thêm/sửa/xóa đi qua đây."""
from django.core.exceptions import ValidationError

from apps.cart.models import Cart, CartItem
from apps.products.models import Product, ProductStatus


def get_or_create_cart(user) -> Cart:
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def add_item(user, product_id, quantity=1) -> CartItem:
    """
    Thêm sản phẩm vào giỏ. Nếu đã có trong giỏ thì CỘNG THÊM số lượng
    (không tạo dòng mới trùng sản phẩm — có unique_together bảo vệ ở DB).
    Kiểm tra tồn kho ngay khi thêm để feedback sớm cho khách, dù vẫn sẽ
    kiểm tra lại lần cuối (kèm lock) ở bước checkout.
    """
    product = Product.objects.select_related("inventory").get(id=product_id)

    if product.status != ProductStatus.ACTIVE:
        raise ValidationError("Sản phẩm hiện không thể mua.")

    cart = get_or_create_cart(user)
    item, created = CartItem.objects.get_or_create(
        cart=cart, product=product, defaults={"quantity": quantity}
    )
    if not created:
        item.quantity += quantity

    if item.quantity > product.inventory.quantity:
        raise ValidationError(
            f"Chỉ còn {product.inventory.quantity} {product.unit} trong kho, "
            f"không thể thêm {item.quantity}."
        )

    item.save()
    return item


def update_item_quantity(user, item_id, quantity) -> CartItem:
    if quantity < 1:
        raise ValidationError("Số lượng phải lớn hơn 0 — dùng API xóa nếu muốn bỏ sản phẩm.")

    item = CartItem.objects.select_related("product__inventory").get(id=item_id, cart__user=user)
    if quantity > item.product.inventory.quantity:
        raise ValidationError(f"Chỉ còn {item.product.inventory.quantity} {item.product.unit} trong kho.")

    item.quantity = quantity
    item.save(update_fields=["quantity", "updated_at"])
    return item


def toggle_selected(user, item_id, selected: bool) -> CartItem:
    item = CartItem.objects.get(id=item_id, cart__user=user)
    item.selected = selected
    item.save(update_fields=["selected", "updated_at"])
    return item


def remove_item(user, item_id):
    CartItem.objects.filter(id=item_id, cart__user=user).delete()
