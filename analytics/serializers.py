
from rest_framework import serializers

from .models import AnalyticsEvent


class AnalyticsEventSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor.email",read_only=True,allow_null=True)
    post_title = serializers.CharField(source="post.title",read_only=True,allow_null=True)

    class Meta:
        model = AnalyticsEvent
        fields = [
            "id",
            "event_type",
            "actor",
            "actor_email",
            "post",
            "post_title",
            "visitor_id",
            "source",
            "metadata",
            "occurred_at",
        ]
        read_only_fields = fields