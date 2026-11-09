from django.db.models import Count, Q
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from engagements.models import Follow

from .models import Post


class AuthorProfileView(APIView):
    """Public profile of a writer: GET /api/v1/blog/authors/<username>/."""

    permission_classes = [AllowAny]

    # ::: get an author's public profile (only people with a published public post)
    def get(self, request, username, *args, **kwargs):
        published = Q(
            posts__status=Post.Status.PUBLISHED,
            posts__visibility=Post.Visibility.PUBLIC,
        )
        author = (
            User.objects.filter(username=username)
            .annotate(post_count=Count("posts", filter=published, distinct=True))
            .first()
        )

        # Readers and writers with nothing published are not shown publicly.
        if not author or author.post_count == 0:
            return Response({"message": "Author not found."}, status=status.HTTP_404_NOT_FOUND)

        avatar = None
        if author.avatar:
            avatar = request.build_absolute_uri(author.avatar.url)

        return Response(
            {
                "id": author.id,
                "username": author.username,
                "name": author.get_full_name(),
                "avatar": avatar,
                "bio": author.bio,
                "date_joined": author.date_joined,
                "post_count": author.post_count,
                "followers_count": Follow.objects.filter(following=author).count(),
            },
            status=status.HTTP_200_OK,
        )