from rest_framework import serializers
from .models import Post, Category, Tag


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id","name","slug","description")

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("id","name","slug")

class PostSerializer(serializers.ModelSerializer):

    author_name = serializers.CharField(source="author.get_full_name",read_only=True)
    category_details = CategorySerializer(source="category",read_only=True)
    tags_details = TagSerializer(source="tags",many=True,read_only=True)

    class Meta:
        model = Post

        fields = (
            "id",
            "title",
            "slug",
            "excerpt",
            "content",
            "featured_image",

            "author",
            "author_name",

            "category",
            "category_details",

            "tags",
            "tags_details",

            "status",
            "visibility",

            "published_at",
            "scheduled_at",

            "created_at",
            "updated_at",

            "views",
            "likes",
            "reading_time",

            "seo_title",
            "seo_description",
            "canonical_url",

            "is_featured",
            "is_trending",
            "allow_comments",
        )

        read_only_fields = (
            "id",
            "author",
            "author_name",
            "published_at",
            "created_at",
            "updated_at",
            "views",
            "likes",
        )