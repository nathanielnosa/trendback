import uuid

from django.conf import settings
from django.db import models


class Notification(models.Model):

    class NotificationType(models.TextChoices):
        COMMENT = "comment", "Comment"
        REPLY = "reply", "Reply"
        REACTION = "reaction", "Reaction"
        BOOKMARK = "bookmark", "Bookmark"
        FOLLOW = "follow", "Follow"
        PUBLISH = "publish", "Publish"

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="notifications")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name="triggered_notifications")
    notification_type = models.CharField(max_length=20,choices=NotificationType.choices)

    title = models.CharField(max_length=255)
    message = models.TextField()
    related_object_id = models.CharField(max_length=255,null=True,blank=True)
    related_url = models.CharField(max_length=500,blank=True)

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(fields=["recipient"]),
            models.Index(fields=["actor"]),
            models.Index(fields=["notification_type"]),
            models.Index(fields=["is_read"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["recipient", "is_read"]),
        ]

    def __str__(self):
        return f"{self.recipient} - {self.title}"