import uuid

from django.conf import settings
from django.db import models


class Media(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="media_files",
    )
    file = models.ImageField(upload_to="library/%Y/%m/", width_field="width", height_field="height")
    thumbnail = models.ImageField(upload_to="library/thumbs/%Y/%m/", blank=True)
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    size = models.PositiveIntegerField(default=0, help_text="File size in bytes")
    content_type = models.CharField(max_length=50)
    original_name = models.CharField(max_length=255)
    alt_text = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "media"

    def __str__(self):
        return self.original_name

    def delete_files(self):
        """Remove the image and thumbnail from storage."""
        if self.file:
            self.file.delete(save=False)
        if self.thumbnail:
            self.thumbnail.delete(save=False)