from django.contrib import admin

from .models import Reaction, Bookmark,Share,Follow

# ::: REACTION
@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ("user","post","reaction_type","created_at","updated_at")
    list_filter = ("reaction_type","created_at")

    search_fields = ("user__email","user__username","post__title")

    readonly_fields = ("id","created_at","updated_at")
    ordering = ("-created_at",)

# ::: BOOKMARK
@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ("user","post","created_at",)
    list_filter = ("created_at",)
    search_fields = ("user__email","user__username","post__title",)
    readonly_fields = ("id","created_at",)
    ordering = ("-created_at",)

# ::: SHARE
@admin.register(Share)
class ShareAdmin(admin.ModelAdmin):
    list_display = ("user","post","platform","created_at",)
    list_filter = ("platform","created_at",)
    search_fields = ("user__email","user__username","post__title",)
    readonly_fields = ("id","created_at",)
    ordering = ("-created_at",)

# ::: FOLLOWERS
@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ("follower","following","created_at")
    list_filter = ("created_at",)
    search_fields = ("follower__email","follower__username","following__email","following__username")
    readonly_fields = ("id","created_at",)
    ordering = ("-created_at",)