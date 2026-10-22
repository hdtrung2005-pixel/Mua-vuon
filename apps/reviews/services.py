"""Service layer cho Review — kiểm tra điều kiện mua hàng + tính thống kê."""
from django.core.exceptions import ValidationError
from django.db.models import Avg, Count

from apps.orders.models import OrderItem, OrderStatus
from apps.reviews.models import Review


class NotPurchasedError(ValidationError):
    pass


def has_purchased_product(user, product_id) -> bool:
    """
    Chỉ tính là 'đã mua' khi đơn hàng chứa sản phẩm này đã DELIVERED —
    không cho đánh giá ngay khi vừa checkout (PENDING) vì chưa nhận hàng thật.
    """
    return OrderItem.objects.filter(
        order__customer=user,
        order__status=OrderStatus.DELIVERED,
        product_id=product_id,
    ).exists()


def create_review(user, product_id, rating, content="", image=None):
    if not has_purchased_product(user, product_id):
        raise NotPurchasedError("Bạn chỉ có thể đánh giá sản phẩm đã mua và nhận hàng thành công.")

    if Review.objects.filter(product_id=product_id, user=user).exists():
        raise ValidationError("Bạn đã đánh giá sản phẩm này rồi — dùng API sửa đánh giá thay vì tạo mới.")

    return Review.objects.create(
        product_id=product_id, user=user, rating=rating, content=content, image=image
    )


def update_review(user, review_id, rating=None, content=None):
    review = Review.objects.get(id=review_id, user=user)
    if rating is not None:
        review.rating = rating
    if content is not None:
        review.content = content
    review.save()
    return review


def delete_review(user, review_id):
    Review.objects.filter(id=review_id, user=user).delete()


def get_rating_summary(product_id) -> dict:
    """Điểm trung bình, số lượt đánh giá, phân bố 1-5 sao — dùng cho trang sản phẩm."""
    qs = Review.objects.filter(product_id=product_id, is_approved=True)
    aggregate = qs.aggregate(average=Avg("rating"), count=Count("id"))

    distribution = {star: 0 for star in range(1, 6)}
    for row in qs.values("rating").annotate(count=Count("id")).order_by():
        distribution[row["rating"]] = row["count"]

    return {
        "average": round(aggregate["average"], 1) if aggregate["average"] else 0,
        "count": aggregate["count"],
        "distribution": distribution,
    }
