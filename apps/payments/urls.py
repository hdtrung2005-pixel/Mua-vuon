from django.urls import path

from apps.payments import views

app_name = "payments"

urlpatterns = [
    path("", views.PaymentListView.as_view(), name="payment-list"),
]
