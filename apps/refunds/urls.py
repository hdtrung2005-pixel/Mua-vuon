from django.urls import path

from apps.refunds import views

app_name = "refunds"

urlpatterns = [
    path("", views.MyRefundRequestListView.as_view(), name="my-refund-list"),
    path("request/", views.CreateRefundRequestView.as_view(), name="create-refund"),
    path("staff/", views.StaffRefundRequestListView.as_view(), name="staff-refund-list"),
    path("<int:refund_id>/approve/", views.ApproveRefundView.as_view(), name="approve-refund"),
    path("<int:refund_id>/reject/", views.RejectRefundView.as_view(), name="reject-refund"),
    path("<int:refund_id>/complete/", views.CompleteRefundView.as_view(), name="complete-refund"),
]
