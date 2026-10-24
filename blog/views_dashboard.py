from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import CanCreatePost, CanReviewPost
from paginations.pagination import PostPagination

from .models import Post
from .serializers import PostSerializer


def _paginated_posts(view, request, posts):
    paginator = PostPagination()
    page = paginator.paginate_queryset(posts, request, view=view)
    serializer = PostSerializer(page, many=True, context={"request": request})
    return paginator.get_paginated_response(serializer.data)


# =============================
# MY POSTS (author dashboard)
# =============================
class MyPostsView(APIView):
    """Every post the logged-in user wrote, in any status."""

    permission_classes = [CanCreatePost]

    def get(self, request, *args, **kwargs):
        posts = (
            Post.objects
            .filter(author=request.user)
            .select_related("author", "category", "reviewed_by")
            .prefetch_related("tags")
        )

        status_filter = request.query_params.get("status")
        if status_filter:
            if status_filter not in Post.Status.values:
                return Response(
                    {"status": "Invalid status."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            posts = posts.filter(status=status_filter)

        search = request.query_params.get("search")
        if search:
            posts = posts.filter(title__icontains=search)

        return _paginated_posts(self, request, posts.order_by("-updated_at"))


# =============================
# REVIEW QUEUE (editors/admins)
# =============================
class ReviewQueueView(APIView):
    """Posts waiting for an editor: under review (default) or approved."""

    permission_classes = [CanReviewPost]
    QUEUE_STATUSES = (Post.Status.UNDER_REVIEW.value, Post.Status.APPROVED.value)

    def get(self, request, *args, **kwargs):
        status_filter = request.query_params.get(
            "status", Post.Status.UNDER_REVIEW.value
        )

        if status_filter not in self.QUEUE_STATUSES:
            return Response(
                {"status": "Use under_review or approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        posts = (
            Post.objects
            .filter(status=status_filter)
            .select_related("author", "category", "reviewed_by")
            .prefetch_related("tags")
            .order_by("updated_at")  # oldest waiting first
        )

        return _paginated_posts(self, request, posts)