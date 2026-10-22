"""API Review — /api/v1/reviews/..."""
from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError
from rest_framework import generics, permissions, status
from rest_framework.exceptions import NotFound, ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.reviews import services
from apps.reviews.models import Review
from apps.reviews.serializers import (
    CreateReviewSerializer,
    ReviewSerializer,
    UpdateReviewSerializer,
)


class ProductReviewListView(generics.ListAPIView):
    """GET /api/v1/reviews/?product=<id> — công khai, ai cũng xem được."""

    serializer_class = ReviewSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = Review.objects.filter(is_approved=True).select_related("user", "product")
        product_id = self.request.query_params.get("product")
        if product_id:
            qs = qs.filter(product_id=product_id)
        return qs


class CreateReviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CreateReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            review = services.create_review(request.user, **serializer.validated_data)
        except DjangoValidationError as exc:
            raise DRFValidationError({"detail": exc.messages if hasattr(exc, "messages") else str(exc)})
        return Response(ReviewSerializer(review).data, status=status.HTTP_201_CREATED)


class ReviewDetailView(APIView):
    """PATCH để sửa, DELETE để xóa — chỉ chủ review."""

    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, review_id):
        serializer = UpdateReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            review = services.update_review(request.user, review_id, **serializer.validated_data)
        except ObjectDoesNotExist:
            raise NotFound("Không tìm thấy đánh giá.")
        return Response(ReviewSerializer(review).data)

    def delete(self, request, review_id):
        services.delete_review(request.user, review_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
