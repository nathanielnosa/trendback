from django.db.models import Count

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from blog.models import Post

from .models import Reaction,Bookmark,Share
from .serializers import ReactionSerializer,BookmarkSerializer,ShareSerializer

# ==========================
# POST REACTION VIEW
# ==========================
class PostReactionView(APIView):
    permission_classes = [IsAuthenticated]

    def get_post(self, post_id):
        try:
            return Post.objects.get(id=post_id,status=Post.Status.PUBLISHED,visibility=Post.Visibility.PUBLIC)
        except Post.DoesNotExist:
            return None
    # ::get reaction
    def get(self, request, post_id,*args,**kwargs):
        post = self.get_post(post_id)

        if not post:
            return Response(
                {"message": "Published post not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        reactions = Reaction.objects.filter(post=post)
        counts = reactions.values("reaction_type").annotate(total=Count("id"))

        reaction_counts = {
            reaction_type: 0
            for reaction_type, _ in Reaction.ReactionType.choices
        }

        for item in counts:
            reaction_counts[item["reaction_type"]] = item["total"]

        user_reaction = reactions.filter(
            user=request.user
        ).first()

        return Response(
            {
                "post": post.id,
                "counts": reaction_counts,
                "user_reaction": (
                    user_reaction.reaction_type
                    if user_reaction
                    else None
                ),
            },
            status=status.HTTP_200_OK
        )
    # :: create reaction
    def post(self, request, post_id,*args,**kwargs):
        post = self.get_post(post_id)

        if not post:
            return Response(
                {"message": "Published post not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        reaction_type = request.data.get("reaction_type")

        if not reaction_type:
            return Response(
                {
                    "reaction_type": (
                        "This field is required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if reaction_type not in dict(
            Reaction.ReactionType.choices
        ):
            return Response(
                {
                    "reaction_type": (
                        "Invalid reaction type."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        reaction = Reaction.objects.filter(
            user=request.user,
            post=post
        ).first()

        if reaction:
            if reaction.reaction_type == reaction_type:
                return Response(
                    {
                        "message": (
                            "You already have this reaction "
                            "on this post."
                        ),
                        "reaction": ReactionSerializer(
                            reaction,
                            context={"request": request}
                        ).data,
                    },
                    status=status.HTTP_200_OK
                )

            reaction.reaction_type = reaction_type
            reaction.save(
                update_fields=[
                    "reaction_type",
                    "updated_at"
                ]
            )

            return Response(
                {
                    "message": "Reaction updated successfully.",
                    "reaction": ReactionSerializer(
                        reaction,
                        context={"request": request}
                    ).data,
                },
                status=status.HTTP_200_OK
            )

        reaction = Reaction.objects.create(
            user=request.user,
            post=post,
            reaction_type=reaction_type
        )

        return Response(
            {
                "message": "Reaction added successfully.",
                "reaction": ReactionSerializer(
                    reaction,
                    context={"request": request}
                ).data,
            },
            status=status.HTTP_201_CREATED
        )
    # ::delete
    def delete(self, request, post_id,*args,**kwargs):
        post = self.get_post(post_id)

        if not post:
            return Response(
                {"message": "Published post not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        reaction = Reaction.objects.filter(
            user=request.user,
            post=post
        ).first()

        if not reaction:
            return Response(
                {
                    "message": (
                        "You have not reacted to this post."
                    )
                },
                status=status.HTTP_404_NOT_FOUND
            )

        reaction.delete()

        return Response(
            {
                "message": (
                    "Reaction removed successfully."
                )
            },
            status=status.HTTP_200_OK
        )

# ==========================
# POST BOOKMARK VIEW
# ==========================
class PostBookmarkView(APIView):
    permission_classes = [IsAuthenticated]

    def get_post(self, post_id):
        try:
            return Post.objects.get(id=post_id,status=Post.Status.PUBLISHED,visibility=Post.Visibility.PUBLIC)
        except Post.DoesNotExist:
            return None
    # :::get bookmark
    def get(self, request, post_id, *args,**kwargs):
        post = self.get_post(post_id)

        if not post:
            return Response(
                {"message": "Published post not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        bookmark = Bookmark.objects.filter(user=request.user,post=post).first()

        return Response(
            {
                "post": post.id,
                "bookmarked": bookmark is not None,
                "bookmark": (
                    BookmarkSerializer(
                        bookmark,
                        context={"request": request}
                    ).data
                    if bookmark
                    else None
                ),
            },
            status=status.HTTP_200_OK
        )
    # ::: post bookmark
    def post(self, request, post_id,*args, **kwargs):
        post = self.get_post(post_id)

        if not post:
            return Response(
                {"message": "Published post not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        bookmark = Bookmark.objects.filter(user=request.user,post=post).first()

        if bookmark:
            return Response(
                {
                    "message": "Post is already bookmarked.",
                    "bookmark": BookmarkSerializer(
                        bookmark,
                        context={"request": request}
                    ).data,
                },
                status=status.HTTP_200_OK
            )

        bookmark = Bookmark.objects.create(
            user=request.user,
            post=post
        )

        return Response(
            {
                "message": "Post bookmarked successfully.",
                "bookmark": BookmarkSerializer(
                    bookmark,
                    context={"request": request}
                ).data,
            },
            status=status.HTTP_201_CREATED
        )
    # ::: delete 
    def delete(self, request, post_id,*args,**kwargs):
        post = self.get_post(post_id)

        if not post:
            return Response(
                {"message": "Published post not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        bookmark = Bookmark.objects.filter(user=request.user,post=post).first()

        if not bookmark:
            return Response(
                {
                    "message": (
                        "You have not bookmarked this post."
                    )
                },
                status=status.HTTP_404_NOT_FOUND
            )

        bookmark.delete()

        return Response(
            {
                "message": "Bookmark removed successfully."
            },
            status=status.HTTP_200_OK
        )

# ==========================
# BOOKMARK LIST VIEW
# ==========================
class BookmarkListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request,*args,**kwargs):
        bookmarks = (Bookmark.objects.filter(user=request.user).select_related("post"))
        serializer = BookmarkSerializer(bookmarks,many=True,context={"request": request})

        return Response(
            {
                "count": bookmarks.count(),
                "bookmarks": serializer.data,
            },
            status=status.HTTP_200_OK
        )

# ==========================
# POST SHARE VIEW
# ==========================
class PostShareView(APIView):
    permission_classes = [IsAuthenticated]

    def get_post(self, post_id):
        try:
            return Post.objects.get(id=post_id,status=Post.Status.PUBLISHED,visibility=Post.Visibility.PUBLIC)
        except Post.DoesNotExist:
            return None

    def post(self, request, post_id,*args,**kwargs):
        post = self.get_post(post_id)
        if not post:
            return Response(
                {"message": "Published post not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = ShareSerializer(
            data={
                "post": post.id,
                "platform": request.data.get("platform"),
            },
            context={"request": request},
        )

        if not serializer.is_valid():
            return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)

        share = serializer.save(user=request.user)

        return Response(
            {
                "message": "Post shared successfully.",
                "share": ShareSerializer(
                    share,
                    context={"request": request}
                ).data,
            },
            status=status.HTTP_201_CREATED
        )

    def get(self, request, post_id,*args,**kwargs):
        post = self.get_post(post_id)

        if not post:
            return Response({"message": "Published post not found."},status=status.HTTP_404_NOT_FOUND)

        shares = Share.objects.filter(post=post)
        platform_counts = shares.values("platform").annotate(total=Count("id"))
        share_counts = {
            platform: 0
            for platform, _ in Share.Platform.choices
        }

        for item in platform_counts:
            share_counts[item["platform"]] = item["total"]

        return Response(
            {
                "post": post.id,
                "total_shares": shares.count(),
                "shares_by_platform": share_counts,
            },
            status=status.HTTP_200_OK
        )