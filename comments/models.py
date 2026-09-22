from django.db import models
from django.conf import settings
import uuid

from blog.models import Post


class Comment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        DELETED = "deleted", "Deleted"

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    post = models.ForeignKey(Post,on_delete=models.CASCADE,related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="comments")
    parent = models.ForeignKey("self",on_delete=models.CASCADE,null=True,blank=True,related_name="replies")
    content = models.TextField()

    status = models.CharField(max_length=20,choices=Status.choices,default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    edited_at = models.DateTimeField(null=True,blank=True)
    likes = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["post"]),
            models.Index(fields=["author"]),
            models.Index(fields=["status"]),
            models.Index(fields=["parent"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.author} - {self.post.title}"