from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView

from accounts.permissions import CanManageComments

from .models import Comment
from .serializers import CommentSerializer


class CommentQueuePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class PendingCommentSerializer(CommentSerializer):
    post_title = serializers.CharField(source="post.title", read_only=True)

    class Meta(CommentSerializer.Meta):
        fields = CommentSerializer.Meta.fields + ("post_title",)
        read_only_fields = CommentSerializer.Meta.read_only_fields + ("post_title",)


# =========================
# PENDING COMMENTS (moderation queue)
# =========================
class PendingCommentsView(APIView):
    """
    Comments waiting for approval.
    Admins and editors see all of them; authors see only the ones
    on their own posts.
    """

    permission_classes = [CanManageComments]

    def get(self, request, *args, **kwargs):
        comments = (
            Comment.objects
            .filter(status=Comment.Status.PENDING)
            .select_related("author", "post", "parent")
        )

        if request.user.role == "AUTHOR":
            comments = comments.filter(post__author=request.user)

        comments = comments.order_by("created_at")  # oldest first

        paginator = CommentQueuePagination()
        page = paginator.paginate_queryset(comments, request, view=self)
        serializer = PendingCommentSerializer(
            page, many=True, context={"request": request}
        )
        return paginator.get_paginated_response(serializer.data)