from django.urls import path

from apps.shipping import views

app_name = "shipping"

urlpatterns = [
    path("", views.ShippingListView.as_view(), name="shipping-list"),
    path("<int:shipping_id>/update-status/", views.UpdateShippingStatusView.as_view(), name="update-status"),
]
