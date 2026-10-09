
from django.contrib import admin

from .models import AnalyticsEvent


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ("id","event_type","actor","post","visitor_id","source","occurred_at")
    list_filter = ("event_type","occurred_at")
    search_fields = ("visitor_id","actor__email","actor__username","post__title","post__slug","source")
    readonly_fields = ("id","occurred_at")

    ordering = ("-occurred_at",)

    date_hierarchy = "occurred_at"

    list_per_page = 50