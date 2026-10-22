"""
Service layer cho Catalog — nơi chứa mọi logic nghiệp vụ + caching.
Views/Serializers chỉ gọi qua đây, không tự viết query hoặc cache logic.
"""
from django.core.cache import cache

from apps.products.models import Category, Product, ProductStatus

CACHE_TTL_SECONDS = 60 * 15  # 15 phút — danh mục/sản phẩm không đổi liên tục
CATEGORY_TREE_CACHE_KEY = "catalog:category_tree"
HOMEPAGE_PRODUCTS_CACHE_KEY = "catalog:homepage_products"


def get_category_tree():
    """
    Trả về danh sách danh mục gốc (parent=None), mỗi danh mục có sẵn
    danh sách con (đã prefetch) — dùng cho menu/homepage.
    Cache lại vì menu danh mục gần như không đổi trong ngày.
    """
    cached = cache.get(CATEGORY_TREE_CACHE_KEY)
    if cached is not None:
        return cached

    categories = list(
        Category.objects.filter(parent__isnull=True, is_active=True)
        .prefetch_related("children")
        .order_by("name")
    )
    cache.set(CATEGORY_TREE_CACHE_KEY, categories, CACHE_TTL_SECONDS)
    return categories


def invalidate_category_cache():
    cache.delete(CATEGORY_TREE_CACHE_KEY)


def get_active_products_queryset():
    """
    Queryset chuẩn cho listing sản phẩm — luôn select_related('category')
    và prefetch_related('images') để tránh N+1 query khi serialize.
    Đây là nơi DUY NHẤT định nghĩa queryset này; view/API chỉ filter thêm
    trên queryset trả về từ đây, không viết lại select_related ở nơi khác.
    """
    return (
        Product.objects.filter(status=ProductStatus.ACTIVE)
        .select_related("category")
        .prefetch_related("images")
    )


def get_homepage_product_ids(limit=12):
    """
    Cache ID sản phẩm hiển thị trang chủ (không cache cả object để tránh
    dữ liệu cũ/stale object trong cache — chỉ cache ID, query lại object
    mới nhất mỗi lần, vẫn nhanh nhờ đã có index).
    """
    cached_ids = cache.get(HOMEPAGE_PRODUCTS_CACHE_KEY)
    if cached_ids is not None:
        return cached_ids

    ids = list(
        get_active_products_queryset().order_by("-created_at").values_list("id", flat=True)[:limit]
    )
    cache.set(HOMEPAGE_PRODUCTS_CACHE_KEY, ids, CACHE_TTL_SECONDS)
    return ids


def invalidate_homepage_products_cache():
    cache.delete(HOMEPAGE_PRODUCTS_CACHE_KEY)


BEST_SELLERS_CACHE_KEY = "catalog:best_sellers"


def get_related_products(product, limit=6):
    """
    Recommendation tiêu chí 1: sản phẩm cùng danh mục (đã chốt — chỉ dùng
    2 tiêu chí đơn giản, không cần machine learning ở bản đầu).
    """
    return (
        get_active_products_queryset()
        .filter(category=product.category)
        .exclude(id=product.id)
        .order_by("-created_at")[:limit]
    )


def get_best_selling_products(limit=8):
    """
    Recommendation tiêu chí 2: sản phẩm bán chạy nhất — tính từ tổng
    quantity trong OrderItem của các đơn ĐÃ GIAO (DELIVERED), không tính
    đơn đang PENDING/CANCELLED để không lệch số liệu.
    Cache 15 phút vì đây là tính toán tổng hợp (aggregate), không rẻ.
    """
    from django.db.models import Sum

    from apps.orders.models import OrderStatus

    cached_ids = cache.get(BEST_SELLERS_CACHE_KEY)
    if cached_ids is not None:
        product_ids = cached_ids
    else:
        product_ids = list(
            Product.objects.filter(
                order_items__order__status=OrderStatus.DELIVERED, status=ProductStatus.ACTIVE
            )
            .annotate(total_sold=Sum("order_items__quantity"))
            .order_by("-total_sold")
            .values_list("id", flat=True)[:limit]
        )
        cache.set(BEST_SELLERS_CACHE_KEY, product_ids, CACHE_TTL_SECONDS)

    # Giữ đúng thứ tự bán chạy (values_list trả list id theo thứ tự, nhưng
    # Product.objects.filter(id__in=...) không đảm bảo giữ thứ tự đó).
    products = {p.id: p for p in get_active_products_queryset().filter(id__in=product_ids)}
    return [products[pid] for pid in product_ids if pid in products]


def invalidate_best_sellers_cache():
    cache.delete(BEST_SELLERS_CACHE_KEY)


def toggle_wishlist(user, product_id) -> bool:
    """Bật/tắt yêu thích. Trả về True nếu vừa THÊM vào wishlist, False nếu vừa BỎ."""
    from apps.products.models import Wishlist

    obj, created = Wishlist.objects.get_or_create(user=user, product_id=product_id)
    if not created:
        obj.delete()
        return False
    return True


def get_wishlist_product_ids(user) -> set:
    """Dùng để hiện trạng thái "đã thích" (icon tô đầy) trên card sản phẩm mà không N+1 query."""
    from apps.products.models import Wishlist

    if not user.is_authenticated:
        return set()
    return set(Wishlist.objects.filter(user=user).values_list("product_id", flat=True))


def get_wishlist_products(user):
    return (
        get_active_products_queryset()
        .filter(wishlisted_by__user=user)
        .order_by("-wishlisted_by__created_at")
    )
