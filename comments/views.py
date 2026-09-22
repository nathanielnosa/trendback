from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Comment
from .serializers import CommentSerializer

from accounts.permissions import CanManageComments

# =========================
# COMMENT LIST CREATE VIEW
# =========================
class CommentListCreateView(APIView):

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]

        if self.request.method == "POST":
            return [IsAuthenticated()]

        return super().get_permissions()

    # :::get all comments
    def get(self, request,*args,**kwargs):
        post_id = request.query_params.get("post")

        comments = (
            Comment.objects
            .filter(
                status=Comment.Status.APPROVED
            )
            .select_related("author", "post", "parent")
        )

        if post_id:
            comments = comments.filter(
                post_id=post_id
            )

        serializer = CommentSerializer(
            comments,
            many=True,
            context={"request": request}
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )
    # ::: create comments
    def post(self, request,*args,**kwargs):
        serializer = CommentSerializer(
            data=request.data,
            context={"request": request}
        )

        if serializer.is_valid():
            serializer.save(
                author=request.user
            )

            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

# =========================
# COMMENT DETAILS VIEW
# =========================
class CommentDetailView(APIView):

    permission_classes = [IsAuthenticated]
    def get_object(self, comment_id):
        try:
            return Comment.objects.select_related(
                "author",
                "post",
                "parent"
            ).get(id=comment_id)
        except Comment.DoesNotExist:
            return None
    # :: patch update
    def patch(self, request, comment_id,*args,**kwargs):
        comment = self.get_object(comment_id)

        if not comment:
            return Response(
                {"message": "Comment not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if comment.author != request.user:
            return Response(
                {"message": "You can only edit your own comments."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = CommentSerializer(
            comment,
            data=request.data,
            partial=True,
            context={"request": request}
        )

        if serializer.is_valid():
            comment = serializer.save(
                edited_at=timezone.now()
            )

            return Response(
                CommentSerializer(
                    comment,
                    context={"request": request}
                ).data,
                status=status.HTTP_200_OK
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
    # ::: delete
    def delete(self, request, comment_id,*args,**kwargs):
        comment = self.get_object(comment_id)

        if not comment:
            return Response({"message": "Comment not found."},status=status.HTTP_404_NOT_FOUND)

        if (
            comment.author != request.user
            and request.user.role not in ["ADMIN", "EDITOR"]
        ):
            return Response(
                {"message": "You do not have permission to delete this comment."},
                status=status.HTTP_403_FORBIDDEN
            )

        comment.status = Comment.Status.DELETED
        comment.save(
            update_fields=["status", "updated_at"]
        )

        return Response(
            {"message": "Comment deleted successfully."},
            status=status.HTTP_200_OK
        )
# =========================
# COMMENT DETAILS VIEW
# =========================