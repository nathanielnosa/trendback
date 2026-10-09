
import uuid

from django.conf import settings
from django.db import models

from blog.models import Post

class AnalyticsEvent(models.Model):

    class EventType(models.TextChoices):
        POST_VIEW = "post_view", "Post View"
        REACTION = "reaction", "Reaction"
        COMMENT = "comment", "Comment"
        SHARE = "share", "Share"
        BOOKMARK = "bookmark", "Bookmark"
        FOLLOW = "follow", "Follow"
        POST_PUBLISHED = "post_published", "Post Published"

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    event_type = models.CharField(max_length=30,choices=EventType.choices,db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True,blank=True,related_name="analytics_events")
    post = models.ForeignKey(Post,on_delete=models.SET_NULL,null=True,blank=True,related_name="analytics_events")
    # Optional identifier for anonymous visitors.
    visitor_id = models.CharField(max_length=100,blank=True,db_index=True)
    # Optional source, such as homepage, search, or external referral.
    source = models.CharField(max_length=100,blank=True)
    # Additional event details, such as the platform used for a share.
    metadata = models.JSONField(default=dict,blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True,db_index=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(
                fields=["event_type", "occurred_at"],
            ),
            models.Index(
                fields=["post", "occurred_at"],
            ),
            models.Index(
                fields=["actor", "occurred_at"],
            ),
        ]

    def __str__(self):
        return f"{self.event_type} - {self.occurred_at}"