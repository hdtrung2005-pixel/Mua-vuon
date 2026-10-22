from django.urls import path

from apps.cart import views

app_name = "cart"

urlpatterns = [
    path("", views.CartView.as_view(), name="cart-detail"),
    path("items/", views.AddCartItemView.as_view(), name="cart-add-item"),
    path("items/<int:item_id>/", views.CartItemDetailView.as_view(), name="cart-item-detail"),
]
