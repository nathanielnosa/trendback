from django.contrib import admin

from .models import Reaction


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ("user","post","reaction_type","created_at","updated_at")
    list_filter = ("reaction_type","created_at")

    search_fields = ("user__email","user__username","post__title")

    readonly_fields = ("id","created_at","updated_at")
    ordering = ("-created_at",)