from django.urls import path

from .views import (
    NotificationListView,
    NotificationDetailView,
    NotificationMarkReadView,
    NotificationMarkAllReadView,
    UnreadNotificationListView
)


urlpatterns = [
    path("",NotificationListView.as_view(),name="notification-list"),
    path("<uuid:notification_id>/",NotificationDetailView.as_view(),name="notification-detail"),
    path("<uuid:notification_id>/read/",NotificationMarkReadView.as_view(),name="notification-mark-read"),
    path("read-all/",NotificationMarkAllReadView.as_view(),name="notification-mark-all-read"),
    path("unread/",UnreadNotificationListView.as_view(),name="notification-unread"),
]