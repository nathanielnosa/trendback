from django.contrib import admin

from .models import Comment

# ::: ADMIN COMMENT
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("content","post","author","parent","status","created_at","updated_at")
    search_fields = ("content","author","parent")



