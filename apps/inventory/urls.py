from django.urls import path

from apps.inventory import views

app_name = "inventory"

urlpatterns = [
    path("", views.InventoryListView.as_view(), name="inventory-list"),
    path("transactions/", views.InventoryTransactionListView.as_view(), name="transaction-list"),
    path("receive/", views.ReceiveStockView.as_view(), name="receive-stock"),
    path("adjust/", views.AdjustStockView.as_view(), name="adjust-stock"),
]
