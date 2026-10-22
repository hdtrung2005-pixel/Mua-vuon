from django.urls import path

from apps.staffpanel import views

app_name = "staffpanel"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("don-hang/", views.order_list, name="order-list"),
    path("don-hang/<str:order_code>/", views.order_detail, name="order-detail"),
    path("danh-muc/", views.category_list, name="category-list"),
    path("san-pham/", views.product_list, name="product-list"),
    path("san-pham/them/", views.product_form, name="product-create"),
    path("san-pham/<int:product_id>/sua/", views.product_form, name="product-edit"),
    path("san-pham/<int:product_id>/anh/<int:image_id>/xoa/", views.product_image_delete, name="product-image-delete"),
    path("ton-kho/", views.inventory_list, name="inventory-list"),
    path("ton-kho/<int:inventory_id>/lich-su/", views.inventory_transactions, name="inventory-transactions"),
    path("hoan-tien/", views.refund_list, name="refund-list"),
    path("doanh-thu/", views.revenue_dashboard, name="revenue"),
]
