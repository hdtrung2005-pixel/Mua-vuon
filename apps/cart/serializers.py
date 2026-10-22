from rest_framework import serializers

from apps.cart.models import Cart, CartItem


class CartItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_slug = serializers.CharField(source="product.slug", read_only=True)
    unit_price = serializers.DecimalField(source="product.effective_price", max_digits=12, decimal_places=2, read_only=True)
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    available_stock = serializers.IntegerField(source="product.inventory.quantity", read_only=True)

    class Meta:
        model = CartItem
        fields = [
            "id", "product", "product_name", "product_slug",
            "quantity", "selected", "unit_price", "subtotal", "available_stock",
        ]


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = Cart
        fields = ["id", "items", "total_amount"]


class AddItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)


class UpdateQuantityInputSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)


class ToggleSelectedInputSerializer(serializers.Serializer):
    selected = serializers.BooleanField()
