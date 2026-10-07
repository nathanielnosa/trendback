from django.db import models
from django.conf import settings
from blog.models import Post
import uuid


class Reaction(models.Model):

    class ReactionType(models.TextChoices):
        LIKE = "like", "Like"
        LOVE = "love", "Love"
        INSIGHTFUL = "insightful", "Insightful"
        HELPFUL = "helpful", "Helpful"

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="reactions")
    post = models.ForeignKey(Post,on_delete=models.CASCADE,related_name="reactions")
    reaction_type = models.CharField(max_length=20,choices=ReactionType.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["user", "post"],
                name="unique_user_post_reaction"
            )
        ]

        indexes = [
            models.Index(fields=["post"]),
            models.Index(fields=["user"]),
            models.Index(fields=["reaction_type"]),
            models.Index(fields=["post", "reaction_type"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.post.title} - {self.reaction_type}"

# ::: BOOKMARK
class Bookmark(models.Model):
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="bookmarks")
    post = models.ForeignKey(Post,on_delete=models.CASCADE,related_name="bookmarks")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["user", "post"],
                name="unique_user_post_bookmark"
            )
        ]

        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["post"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.post.title}"
    
# ::: SHARE
class Share(models.Model):

    class Platform(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"
        INSTAGRAM = "instagram", "instagram"
        FACEBOOK = "facebook", "Facebook"
        TWITTER = "twitter", "Twitter"
        LINKEDIN = "linkedin", "LinkedIn"
        TELEGRAM = "telegram", "Telegram"
        COPY_LINK = "copy_link", "Copy Link"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="shares")
    post = models.ForeignKey(Post,on_delete=models.CASCADE,related_name="shares")
    platform = models.CharField(max_length=20,choices=Platform.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["post"]),
            models.Index(fields=["platform"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["post", "platform"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.post.title} - {self.platform}"