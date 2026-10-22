from rest_framework import serializers

from apps.reviews.models import Review


class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = Review
        fields = ["id", "product", "user_name", "rating", "content", "image", "created_at"]
        read_only_fields = ["id", "user_name", "created_at"]


class CreateReviewSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    rating = serializers.IntegerField(min_value=1, max_value=5)
    content = serializers.CharField(required=False, allow_blank=True, default="")


class UpdateReviewSerializer(serializers.Serializer):
    rating = serializers.IntegerField(min_value=1, max_value=5, required=False)
    content = serializers.CharField(required=False, allow_blank=True)
