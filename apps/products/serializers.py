from rest_framework import serializers

from apps.products.models import Category, Product, ProductImage


class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "parent", "children"]

    def get_children(self, obj):
        # obj.children đã được prefetch_related ở service layer — không query thêm
        return CategoryChildSerializer(obj.children.all(), many=True).data


class CategoryChildSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image", "is_primary"]


class ProductListSerializer(serializers.ModelSerializer):
    """Dùng cho danh sách sản phẩm — nhẹ, không load hết description dài."""

    category_name = serializers.CharField(source="category.name", read_only=True)
    effective_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "sku", "name", "slug", "category_name",
            "price", "discount_price", "effective_price", "unit",
            "status", "primary_image",
        ]

    def get_primary_image(self, obj):
        # obj.images đã prefetch_related — lấy trong Python, không query lại DB
        images = list(obj.images.all())
        primary = next((img for img in images if img.is_primary), images[0] if images else None)
        return ProductImageSerializer(primary).data if primary else None


class ProductDetailSerializer(serializers.ModelSerializer):
    category = CategoryChildSerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    effective_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    rating_summary = serializers.SerializerMethodField()
    related_products = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "sku", "name", "slug", "description", "category",
            "price", "discount_price", "effective_price", "unit",
            "origin", "status", "images", "rating_summary", "related_products", "created_at",
        ]

    def get_rating_summary(self, obj):
        from apps.reviews.services import get_rating_summary
        return get_rating_summary(obj.id)

    def get_related_products(self, obj):
        from apps.products.services import get_related_products
        return ProductListSerializer(get_related_products(obj), many=True).data
