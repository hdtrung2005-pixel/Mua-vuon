from django.urls import path

from apps.orders import views

app_name = "orders"

urlpatterns = [
    path("", views.OrderListView.as_view(), name="order-list"),
    path("checkout/", views.CheckoutView.as_view(), name="checkout"),
    path("<str:order_code>/", views.OrderDetailView.as_view(), name="order-detail"),
    path("<str:order_code>/cancel/", views.CancelOrderView.as_view(), name="order-cancel"),
]
