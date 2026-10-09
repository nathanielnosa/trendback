from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    recipient_name = serializers.CharField(source="recipient.username",read_only=True)
    actor_name = serializers.CharField(source="actor.username",read_only=True,allow_null=True)

    class Meta:
        model = Notification

        fields = [
            "id",
            "recipient",
            "recipient_name",
            "actor",
            "actor_name",
            "notification_type",
            "title",
            "message",
            "related_object_id",
            "related_url",
            "is_read",
            "read_at",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "recipient",
            "recipient_name",
            "actor",
            "actor_name",
            "notification_type",
            "title",
            "message",
            "related_object_id",
            "related_url",
            "is_read",
            "read_at",
            "created_at",
        ]