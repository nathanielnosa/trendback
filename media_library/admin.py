from django.contrib import admin

from .models import Media


@admin.register(Media)
class MediaAdmin(admin.ModelAdmin):
    list_display = ("original_name", "uploaded_by", "width", "height", "size", "created_at")
    search_fields = ("original_name", "alt_text")
    readonly_fields = ("width", "height", "size", "content_type")