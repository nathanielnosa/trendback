from rest_framework import serializers

from . import services
from .models import Media


class MediaSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    uploaded_by = serializers.SerializerMethodField()

    class Meta:
        model = Media
        fields = [
            "id", "url", "thumbnail_url", "alt_text", "original_name",
            "width", "height", "size", "content_type", "uploaded_by", "created_at",
        ]
        read_only_fields = fields

    def _absolute(self, file):
        if not file:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(file.url) if request else file.url

    def get_url(self, obj):
        return self._absolute(obj.file)

    def get_thumbnail_url(self, obj):
        return self._absolute(obj.thumbnail)

    def get_uploaded_by(self, obj):
        return obj.uploaded_by.username if obj.uploaded_by else None


class MediaUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    alt_text = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")

    def validate_file(self, upload):
        try:
            services.inspect_image(upload)
        except ValueError as error:
            raise serializers.ValidationError(str(error))
        return upload


class MediaUpdateSerializer(serializers.Serializer):
    alt_text = serializers.CharField(max_length=255, allow_blank=True)