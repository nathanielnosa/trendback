from rest_framework import serializers

from .models import Reaction, Bookmark, Share, Follow
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
    post_slug = serializers.CharField(source="post.slug",read_only=True)
    post_excerpt = serializers.CharField(source="post.excerpt",read_only=True)
    post_author_name = serializers.CharField(source="post.author.get_full_name",read_only=True)
    post_published_at = serializers.DateTimeField(source="post.published_at",read_only=True)
    post_reading_time = serializers.IntegerField(source="post.reading_time",read_only=True)
    post_featured_image = serializers.SerializerMethodField()

    class Meta:
        model = Bookmark

        fields = (
            "id","user","user_name",
            "post","post_title","post_slug","post_excerpt",
            "post_author_name","post_published_at","post_reading_time","post_featured_image",
            "created_at",
        )
        read_only_fields = fields

    # ::: the story's picture as a full address, or None when it has none
    # def get_post_featured_image(self, obj):
    #     image = obj.post.featured_image
    #     if not image:
    #         return None
    #     request = self.context.get("request")
    #     return request.build_absolute_uri(image.url) if request else image.url
    def get_post_featured_image(self, obj):
        return obj.post.featured_image or None

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

# ::: FOLLOWERS
class FollowSerializer(serializers.ModelSerializer):

    follower_name = serializers.CharField(source="follower.get_full_name",read_only=True)
    following_name = serializers.CharField(source="following.get_full_name", read_only=True)

    class Meta:
        model = Follow

        fields = ("id","follower","follower_name","following","following_name","created_at")
        read_only_fields = ("id","follower","follower_name","following_name","created_at")

    def validate(self, attrs):
        request = self.context.get("request")
        following = attrs.get("following")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Authentication is required to follow an author."
            )
        if following.role not in [
            "ADMIN",
            "EDITOR",
            "AUTHOR",
        ]:
            raise serializers.ValidationError(
                {
                    "following": (
                        "You can only follow authors, "
                        "editors, or administrators."
                    )
                }
            )

        if not following:
            raise serializers.ValidationError(
                {"following": "User to follow is required."}
            )

        if following == request.user:
            raise serializers.ValidationError(
                {
                    "following": (
                        "You cannot follow yourself."
                    )
                }
            )

        return attrs