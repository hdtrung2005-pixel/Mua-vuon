from django.urls import path

from apps.storefront import views

app_name = "storefront"

urlpatterns = [
    path("", views.home, name="home"),
    path("san-pham/", views.product_list, name="product-list"),
    path("dang-ky/", views.register, name="register"),
    path("gio-hang/", views.cart, name="cart"),
    path("yeu-thich/", views.wishlist, name="wishlist"),
    path("dia-chi/", views.address_list, name="address-list"),
    path("thanh-toan/", views.checkout, name="checkout"),
    path("don-hang/", views.order_list, name="order-list"),
    path("don-hang/<str:order_code>/", views.order_detail, name="order-detail"),
    path("san-pham/<slug:slug>/", views.product_detail, name="product-detail"),
]
