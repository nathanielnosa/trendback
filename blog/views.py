from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from accounts.permissions import (
    CanCreatePost,
    CanEditPost,
    CanDeletePost,
    IsAdmin,
    IsEditor,
)

from .models import Post, Category, Tag
from .serializers import (
    PostSerializer,
    CategorySerializer,
    TagSerializer,
)


# =============================
# POST LIST / CREATE
# =============================

class PostListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]

        if self.request.method == "POST":
            return [CanCreatePost()]

        return super().get_permissions()

    # :::get all post
    def get(self, request,*args,**kwargs):
        posts = (Post.objects.select_related("author", "category").prefetch_related("tags"))
        serializer = PostSerializer(posts, many=True)
        return Response(serializer.data,status=status.HTTP_200_OK)

    # :::create post
    def post(self, request,*args,**kwargs):
        serializer = PostSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(author=request.user)
            return Response(serializer.data,status=status.HTTP_201_CREATED)

        return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)


# ==========================
# POST DETAIL
# ==========================

class PostDetailView(APIView):
    def get_permissions(self):

        if self.request.method == "GET":
            return [AllowAny()]

        if self.request.method in ["PUT", "PATCH"]:
            return [CanEditPost()]

        if self.request.method == "DELETE":
            return [CanDeletePost()]

        return super().get_permissions()

    # ::: function to get object
    def get_object(self, post_id):

        try:
            return (Post.objects.select_related("author", "category").prefetch_related("tags").get(id=post_id))
        except Post.DoesNotExist:
            return None

    # ::: get a post
    def get(self, request, post_id,*args ,**kwargs):
        post = self.get_object(post_id)
        if not post:
            return Response({"message": "Post not found."},status=status.HTTP_404_NOT_FOUND)

        serializer = PostSerializer(post)
        return Response(serializer.data,status=status.HTTP_200_OK)

    # ::: update a post
    def put(self, request, post_id,*args,**kwargs):
        post = self.get_object(post_id)

        if not post:
            return Response({"message": "Post not found."},status=status.HTTP_404_NOT_FOUND)
        # check permission not all can update
        self.check_object_permissions(request, post)
        serializer = PostSerializer(post,data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)

    # ::: partial update
    def patch(self, request, post_id,*args,**kwargs):
        post = self.get_object(post_id)

        if not post:
            return Response({"message": "Post not found."},status=status.HTTP_404_NOT_FOUND)

        self.check_object_permissions(request, post)

        serializer = PostSerializer(post,data=request.data,partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)

    # ::: Delete a post
    def delete(self, request, post_id,*args,**kwargs):

        post = self.get_object(post_id)

        if not post:
            return Response(
                {"message": "Post not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        self.check_object_permissions(request, post)

        post.delete()

        return Response(
            {"message": "Post deleted successfully."},
            status=status.HTTP_204_NO_CONTENT
        )


# ===============================
# CATEGORY LIST / CREATE
# ===============================

class CategoryListCreateView(APIView):

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]

        if self.request.method == "POST":
            return [IsEditor()]

        return super().get_permissions()

    def get(self, request, *args,**kwargs):

        categories = Category.objects.all()

        serializer = CategorySerializer(
            categories,
            many=True
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    def post(self, request,*args,**kwargs):

        serializer = CategorySerializer(
            data=request.data
        )

        if serializer.is_valid():
            serializer.save()

            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

# =========================
# CATEGORY DETAIL
# =========================

class CategoryDetailView(APIView):

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]

        if self.request.method in ["PUT", "PATCH", "DELETE"]:
            return [IsEditor()]

        return super().get_permissions()

    def get_object(self, category_id):

        try:
            return Category.objects.get(id=category_id)

        except Category.DoesNotExist:
            return None

    def get(self, request, category_id,*args,**kwargs):

        category = self.get_object(category_id)

        if not category:
            return Response(
                {"message": "Category not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = CategorySerializer(category)

        return Response(serializer.data)

    def put(self, request, category_id,*args,**kwargs):

        category = self.get_object(category_id)

        if not category:
            return Response(
                {"message": "Category not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = CategorySerializer(
            category,
            data=request.data
        )

        if serializer.is_valid():
            serializer.save()

            return Response(serializer.data)

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    def patch(self, request, category_id,*args,**kwargs):

        category = self.get_object(category_id)

        if not category:
            return Response(
                {"message": "Category not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = CategorySerializer(
            category,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()

            return Response(serializer.data)

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request, category_id,*args,**kwargs):

        category = self.get_object(category_id)

        if not category:
            return Response(
                {"message": "Category not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        category.delete()

        return Response(
            {"message": "Category deleted successfully."},
            status=status.HTTP_204_NO_CONTENT
        )


# ============================
# TAG LIST / CREATE
# ============================

class TagListCreateView(APIView):

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]

        if self.request.method == "POST":
            return [IsEditor()]

        return super().get_permissions()

    def get(self, request,*args,**kwargs):

        tags = Tag.objects.all()

        serializer = TagSerializer(
            tags,
            many=True
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    def post(self, request,*args,**kwargs):

        serializer = TagSerializer(
            data=request.data
        )

        if serializer.is_valid():
            serializer.save()

            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )


# ===========================
# TAG DETAIL
# ===========================

class TagDetailView(APIView):

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]

        if self.request.method in ["PUT", "PATCH", "DELETE"]:
            return [IsEditor()]

        return super().get_permissions()

    def get_object(self, tag_id):

        try:
            return Tag.objects.get(id=tag_id)

        except Tag.DoesNotExist:
            return None

    def get(self, request, tag_id,*args,**kwargs):

        tag = self.get_object(tag_id)

        if not tag:
            return Response(
                {"message": "Tag not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = TagSerializer(tag)

        return Response(serializer.data)

    def put(self, request, tag_id,*args,**kwargs):

        tag = self.get_object(tag_id)

        if not tag:
            return Response(
                {"message": "Tag not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = TagSerializer(
            tag,
            data=request.data
        )

        if serializer.is_valid():
            serializer.save()

            return Response(serializer.data)

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    def patch(self, request, tag_id,*args,**kwargs):

        tag = self.get_object(tag_id)
        if not tag:
            return Response(
                {"message": "Tag not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = TagSerializer(
            tag,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()

            return Response(serializer.data)

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request, tag_id,*args,**kwargs):

        tag = self.get_object(tag_id)

        if not tag:
            return Response(
                {"message": "Tag not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        tag.delete()

        return Response(
            {"message": "Tag deleted successfully."},
            status=status.HTTP_204_NO_CONTENT
        )