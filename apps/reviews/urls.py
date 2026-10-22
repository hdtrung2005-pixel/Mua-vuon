from django.urls import path

from apps.reviews import views

app_name = "reviews"

urlpatterns = [
    path("", views.ProductReviewListView.as_view(), name="review-list"),
    path("create/", views.CreateReviewView.as_view(), name="review-create"),
    path("<int:review_id>/", views.ReviewDetailView.as_view(), name="review-detail"),
]
