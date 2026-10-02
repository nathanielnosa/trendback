from django.db.models import Count

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from blog.models import Post

from .models import Reaction
from .serializers import ReactionSerializer

# ==========================
# POST REACTION VIEW
# ==========================
class PostReactionView(APIView):
    permission_classes = [IsAuthenticated]

    def get_post(self, post_id):
        try:
            return Post.objects.get(
                id=post_id,
                status=Post.Status.PUBLISHED,
                visibility=Post.Visibility.PUBLIC,
            )
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

        reactions = Reaction.objects.filter(
            post=post
        )

        counts = reactions.values(
            "reaction_type"
        ).annotate(
            total=Count("id")
        )

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