from rest_framework import serializers
from .models import Post, Category, Tag

# ::: Category Serializer
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id","name","slug","description")

# ::: Tag Serializer
class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ("id","name","slug")

# ::: Post Serializer
class PostSerializer(serializers.ModelSerializer):

    author_name = serializers.CharField(source="author.get_full_name",read_only=True)
    category_details = CategorySerializer(source="category",read_only=True)
    tags_details = TagSerializer(source="tags",many=True,read_only=True)
    reviewed_at = serializers.DateTimeField(read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.get_full_name",read_only=True,)

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

            "reviewed_at",
            "reviewed_by",
            "reviewed_by_name",
            "review_notes",

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
            "slug",
            "author_name",
            "published_at",
            "reviewed_at",
            "reviewed_by",
            "reviewed_by_name",
            "created_at",
            "updated_at",
            "views",
            "likes",
        )
    # featured image validation
    def validate_featured_image(self, value):
        if value:
            if not value.startswith(("http://", "https://")):
                raise serializers.ValidationError(
                    "Featured image must be a valid HTTP or HTTPS URL."
                )

        return value
    # validate for draft post
    def validate(self, attrs):
        request = self.context.get("request")

        if request and request.user.is_authenticated:

            status_value = attrs.get(
                "status",
                Post.Status.DRAFT
            )

            if request.user.role in [
                "AUTHOR",
                "CONTRIBUTOR",
            ]:
                if status_value != Post.Status.DRAFT:
                    raise serializers.ValidationError({
                        "status": (
                            "Authors and contributors can only "
                            "create posts as drafts."
                        )
                    })

        return attrs

# Review Post Serializer
class PostReviewSerializer(serializers.Serializer):

    action = serializers.ChoiceField(
        choices=["approve", "reject"]
    )
    review_notes = serializers.CharField(required=False,allow_blank=True)

    def validate(self, attrs):

        action = attrs.get("action")
        review_notes = attrs.get("review_notes", "").strip()

        if action == "reject" and not review_notes:
            raise serializers.ValidationError({
                "review_notes": "Review notes are required when rejecting a post."
            })

        return attrs

# Post Publish Serializer
class PostPublishSerializer(serializers.Serializer):

    action = serializers.ChoiceField(
        choices=["publish", "schedule"]
    )

    scheduled_at = serializers.DateTimeField(
        required=False,
        allow_null=True
    )

    def validate(self, attrs):

        action = attrs.get("action")
        scheduled_at = attrs.get("scheduled_at")

        if action == "schedule" and not scheduled_at:
            raise serializers.ValidationError({
                "scheduled_at": (
                    "Scheduled date and time are required "
                    "when scheduling a post."
                )
            })

        if action == "publish" and scheduled_at:
            raise serializers.ValidationError({
                "scheduled_at": (
                    "scheduled_at should not be provided "
                    "when publishing immediately."
                )
            })

        return attrs

# Post Submit Review
class PostSubmitReviewSerializer(serializers.Serializer):

    action = serializers.ChoiceField(
        choices=["submit"]
    )