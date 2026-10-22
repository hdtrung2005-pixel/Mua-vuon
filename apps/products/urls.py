from django.urls import path

from apps.products import views

app_name = "products"

urlpatterns = [
    path("categories/", views.CategoryListView.as_view(), name="category-list"),
    path("products/", views.ProductListView.as_view(), name="product-list"),
    path("products/best-sellers/", views.BestSellersView.as_view(), name="best-sellers"),
    path("products/<slug:slug>/", views.ProductDetailView.as_view(), name="product-detail"),
]
