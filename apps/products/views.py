"""
API views cho Catalog — /api/v1/categories/, /api/v1/products/.
Read-only ở Phase 2 (CRUD sản phẩm dành cho ADMIN sẽ làm ở Phase sau
cùng với Inventory, vì tạo sản phẩm cần đồng bộ với tồn kho).
"""
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, permissions

from apps.products.filters import ProductFilter
from apps.products.models import Product
from apps.products.serializers import (
    CategorySerializer,
    ProductDetailSerializer,
    ProductListSerializer,
)
from apps.products.services import get_active_products_queryset, get_best_selling_products, get_category_tree


class CategoryListView(generics.ListAPIView):
    """Danh sách danh mục gốc + danh mục con — lấy từ cache (services.get_category_tree)."""

    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None  # danh mục ít, không cần phân trang

    def get_queryset(self):
        return get_category_tree()


class ProductListView(generics.ListAPIView):
    """
    Danh sách sản phẩm — hỗ trợ:
    - filter: ?category=1 / ?category_slug=rau-cu / ?min_price=&max_price=&in_stock_only=true
    - search: ?search=<tên hoặc SKU>
    - ordering: ?ordering=price / ?ordering=-created_at
    """

    serializer_class = ProductListSerializer
    permission_classes = [permissions.AllowAny]
    queryset = get_active_products_queryset()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ["name", "sku"]
    ordering_fields = ["price", "created_at", "name"]
    ordering = ["-created_at"]


class BestSellersView(generics.ListAPIView):
    """Sản phẩm bán chạy nhất — dùng cho trang chủ (tiêu chí recommendation #2 đã chốt)."""

    serializer_class = ProductListSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None

    def get_queryset(self):
        return get_best_selling_products()


class ProductDetailView(generics.RetrieveAPIView):
    """Chi tiết sản phẩm theo slug (URL đẹp hơn theo id) — kèm rating_summary + related_products."""

    serializer_class = ProductDetailSerializer
    permission_classes = [permissions.AllowAny]

    def get_object(self):
        return get_object_or_404(
            get_active_products_queryset(), slug=self.kwargs["slug"]
        )
