from django.contrib import admin

from apps.reviews.models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["product", "user", "rating", "is_approved", "created_at"]
    list_filter = ["rating", "is_approved"]
    list_select_related = ["product", "user"]
    search_fields = ["product__name", "user__email"]
    list_editable = ["is_approved"]  # ADMIN ẩn review vi phạm ngay trên list, không cần vào từng cái
