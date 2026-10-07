from rest_framework import serializers

from .models import Reaction,Bookmark,Share
from blog.models import Post

# ::: REACTION
class ReactionSerializer(serializers.ModelSerializer):

    user_name = serializers.CharField(source="user.get_full_name",read_only=True)

    post_title = serializers.CharField(source="post.title",read_only=True)

    class Meta:
        model = Reaction

        fields = ("id","user","user_name","post","post_title","reaction_type","created_at","updated_at")

        read_only_fields = ("id","user","user_name","post_title","created_at","updated_at")

    def validate(self, attrs):
        request = self.context.get("request")
        post = attrs.get("post")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Authentication is required to react to a post."
            )

        if not post:
            raise serializers.ValidationError(
                {"post": "Post is required."}
            )

        if post.status != Post.Status.PUBLISHED:
            raise serializers.ValidationError(
                {
                    "post": (
                        "You can only react to published posts."
                    )
                }
            )

        if post.visibility != Post.Visibility.PUBLIC:
            raise serializers.ValidationError(
                {
                    "post": (
                        "You can only react to public posts."
                    )
                }
            )

        return attrs

# ::: BOOKMARK
class BookmarkSerializer(serializers.ModelSerializer):

    user_name = serializers.CharField(source="user.get_full_name",read_only=True)
    post_title = serializers.CharField(source="post.title",read_only=True)
    class Meta:
        model = Bookmark

        fields = ("id","user","user_name","post","post_title","created_at")
        read_only_fields = ("id","user","user_name","post_title","created_at")

    def validate(self, attrs):
        request = self.context.get("request")
        post = attrs.get("post")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Authentication is required to bookmark a post."
            )

        if not post:
            raise serializers.ValidationError(
                {"post": "Post is required."}
            )

        if post.status != Post.Status.PUBLISHED:
            raise serializers.ValidationError(
                {
                    "post": (
                        "You can only bookmark published posts."
                    )
                }
            )

        if post.visibility != Post.Visibility.PUBLIC:
            raise serializers.ValidationError(
                {
                    "post": (
                        "You can only bookmark public posts."
                    )
                }
            )

        return attrs

# ::: SHARE
class ShareSerializer(serializers.ModelSerializer):

    user_name = serializers.CharField(source="user.get_full_name",read_only=True)

    post_title = serializers.CharField(source="post.title",read_only=True)

    class Meta:
        model = Share
        fields = ("id","user","user_name","post","post_title","platform","created_at")

        read_only_fields = ("id","user","user_name","post_title","created_at")

    def validate(self, attrs):
        request = self.context.get("request")
        post = attrs.get("post")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Authentication is required to share a post."
            )

        if not post:
            raise serializers.ValidationError(
                {"post": "Post is required."}
            )

        if post.status != Post.Status.PUBLISHED:
            raise serializers.ValidationError(
                {
                    "post": (
                        "You can only share published posts."
                    )
                }
            )

        if post.visibility != Post.Visibility.PUBLIC:
            raise serializers.ValidationError(
                {
                    "post": (
                        "You can only share public posts."
                    )
                }
            )

        return attrs
