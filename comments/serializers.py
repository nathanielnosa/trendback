from rest_framework import serializers

from .models import Comment
from blog.models import Post


class CommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.get_full_name",read_only=True)
    replies_count = serializers.IntegerField(source="replies.count",read_only=True)

    class Meta:
        model = Comment
        fields = (
            "id",
            "post",
            "author",
            "author_name",
            "parent",
            "content",
            "status",
            "created_at",
            "updated_at",
            "edited_at",
            "likes",
            "replies_count",
        )

        read_only_fields = (
            "id",
            "author",
            "author_name",
            "status",
            "created_at",
            "updated_at",
            "edited_at",
            "likes",
            "replies_count",
        )

    def validate(self, attrs):
        request = self.context.get("request")
        post = attrs.get("post")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Authentication is required to comment."
            )

        if not post:
            raise serializers.ValidationError(
                {"post": "Post is required."}
            )

        if post.status != Post.Status.PUBLISHED:
            raise serializers.ValidationError(
                {"post": "Comments are only allowed on published posts."}
            )

        if post.visibility != Post.Visibility.PUBLIC:
            raise serializers.ValidationError(
                {"post": "Comments are only allowed on public posts."}
            )

        if not post.allow_comments:
            raise serializers.ValidationError(
                {"post": "Comments are disabled for this post."}
            )

        parent = attrs.get("parent")

        if parent:
            if parent.post_id != post.id:
                raise serializers.ValidationError(
                    {
                        "parent": (
                            "The parent comment must belong "
                            "to the same post."
                        )
                    }
                )

            if parent.status != Comment.Status.APPROVED:
                raise serializers.ValidationError(
                    {
                        "parent": (
                            "You can only reply to an approved comment."
                        )
                    }
                )

        return attrs