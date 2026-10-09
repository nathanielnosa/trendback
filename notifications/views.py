from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer
from paginations.pagination import NotificationPagination

# ==========================
# NOTIFICATION LIST
# ==========================
class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]
    # get all notification
    def get(self, request,*args,**kwargs):
        notifications = Notification.objects.filter(recipient=request.user)

        is_read = request.query_params.get("is_read")
        notification_type = request.query_params.get("type")

        if is_read is not None:
            if is_read.lower() == "true":
                notifications = notifications.filter(is_read=True)

            elif is_read.lower() == "false":
                notifications = notifications.filter(is_read=False)

        if notification_type:
            notifications = notifications.filter(
                notification_type=notification_type
            )
        unread_count = Notification.objects.filter(recipient=request.user,is_read=False).count()

        paginator = NotificationPagination()
        page = paginator.paginate_queryset(notifications,request,view=self)
        serializer = NotificationSerializer(page,many=True)

        return Response(
            {
                "count": notifications.count(),
                "unread_count": unread_count,
                "notifications": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

# ==========================
# NOTIFICATION DETAIL
# ==========================
class NotificationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, notification_id,*args,**kwargs):
        notification = get_object_or_404(Notification,id=notification_id,recipient=request.user,)
        serializer = NotificationSerializer(notification)
        return Response(serializer.data,status=status.HTTP_200_OK)

# ==========================
# NOTIFICATION READ VIEW
# ==========================
class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, notification_id,*args,**kwargs):
        notification = get_object_or_404(Notification,id=notification_id,recipient=request.user)

        if not notification.is_read:
            from django.utils import timezone

            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at"])

        serializer = NotificationSerializer(notification)

        return Response(
            {
                "message": "Notification marked as read.",
                "notification": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

# ==========================
# NOTIFICATION MARK ALL VIEW
# ==========================
class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request,*args,**kwargs):
        from django.utils import timezone

        updated_count = Notification.objects.filter(recipient=request.user,is_read=False,).update(is_read=True,read_at=timezone.now())
        return Response(
            {
                "message": "All notifications marked as read.",
                "updated_count": updated_count,
            },
            status=status.HTTP_200_OK,
        )

# ==========================
# UNREAD NOTIFICATION VIEW
# ==========================
class UnreadNotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request,*args,**kwargs):
        notifications = Notification.objects.filter(recipient=request.user,is_read=False)
        serializer = NotificationSerializer(notifications,many=True)

        return Response(
            {
                "count": notifications.count(),
                "notifications": serializer.data,
            },
            status=status.HTTP_200_OK,
        )