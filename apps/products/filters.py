"""Filter cho API sản phẩm — lọc theo danh mục, khoảng giá, trạng thái."""
import django_filters

from apps.products.models import Product, ProductStatus


class ProductFilter(django_filters.FilterSet):
    category = django_filters.NumberFilter(field_name="category_id")
    category_slug = django_filters.CharFilter(field_name="category__slug")
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    in_stock_only = django_filters.BooleanFilter(method="filter_in_stock")

    class Meta:
        model = Product
        fields = ["category", "category_slug", "min_price", "max_price", "in_stock_only"]

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.exclude(status=ProductStatus.OUT_OF_STOCK)
        return queryset
