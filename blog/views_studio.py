import uuid

from django.core.files.storage import default_storage
from django.db.models import Q
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import CanCreatePost

from .models import MediaAsset, Post
from .serializers import PostSerializer

# Largest picture a writer may upload, in bytes (5 MB).
MAX_IMAGE_BYTES = 5 * 1024 * 1024

# Picture formats we accept, and the file ending we save each one with.
IMAGE_FORMATS = {"JPEG": "jpg", "PNG": "png", "GIF": "gif", "WEBP": "webp"}


# =============================
# MY POST (one post, any status)
# =============================
class MyPostDetailView(APIView):
    """Read one post for editing: your own in any status; editors and admins can read any."""

    permission_classes = [CanCreatePost]

    # ::: get a single post, including drafts
    def get(self, request, post_id, *args, **kwargs):
        post = (
            Post.objects.select_related("author", "category", "reviewed_by")
            .prefetch_related("tags")
            .filter(id=post_id)
            .first()
        )

        can_see = post and (
            post.author_id == request.user.id or request.user.role in ("ADMIN", "EDITOR")
        )
        if not can_see:
            return Response({"message": "Post not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(PostSerializer(post, context={"request": request}).data)


# =============================
# MEDIA UPLOAD (pictures for posts)
# =============================
class MediaPagination(PageNumberPagination):
    """The media library shows 24 pictures at a time."""

    page_size = 24
    page_size_query_param = "page_size"
    max_page_size = 60


def media_data(asset):
    """The fields the library page needs for one picture."""
    return {
        "id": str(asset.id),
        "url": asset.url,
        "size": asset.size,
        "created_at": asset.created_at,
    }

# =============================
# MEDIA UPLOAD
# =============================
class MediaUploadView(APIView):
    """Upload one picture (POST) or list the pictures you uploaded (GET)."""

    permission_classes = [CanCreatePost]
    parser_classes = [MultiPartParser, FormParser]

    # ::: list my uploaded pictures, newest first
    def get(self, request, *args, **kwargs):
        assets = MediaAsset.objects.filter(owner=request.user)
        paginator = MediaPagination()
        page = paginator.paginate_queryset(assets, request, view=self)
        return paginator.get_paginated_response([media_data(asset) for asset in page])

    # ::: check and store an uploaded picture
    def post(self, request, *args, **kwargs):
        upload = request.FILES.get("file")

        if not upload:
            return Response({"file": "No file was sent."}, status=status.HTTP_400_BAD_REQUEST)

        if upload.size > MAX_IMAGE_BYTES:
            return Response({"file": "The picture is larger than 5 MB."}, status=status.HTTP_400_BAD_REQUEST)

        # Open it as a real picture; this catches files that only pretend to be images.
        try:
            image = Image.open(upload)
            image_format = image.format
            image.verify()
        except Exception:
            return Response({"file": "This file is not a valid picture."}, status=status.HTTP_400_BAD_REQUEST)

        if image_format not in IMAGE_FORMATS:
            return Response(
                {"file": "Use a JPG, PNG, GIF or WebP picture."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # verify() used the file up, so go back to the start before saving it.
        upload.seek(0)
        name = f"posts/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.{IMAGE_FORMATS[image_format]}"
        saved = default_storage.save(name, upload)
        url = request.build_absolute_uri(default_storage.url(saved))

        asset = MediaAsset.objects.create(owner=request.user, url=url, path=saved, size=upload.size)

        return Response(
            {**media_data(asset), "name": saved},
            status=status.HTTP_201_CREATED,
        )


# =============================
# MEDIA DETAIL (delete one picture)
# =============================
class MediaDetailView(APIView):
    """Delete one picture you uploaded (admins can delete any), unless a post still uses it."""

    permission_classes = [CanCreatePost]

    # ::: delete a picture from the library and from storage
    def delete(self, request, asset_id, *args, **kwargs):
        asset = MediaAsset.objects.filter(id=asset_id).first()

        if not asset or (asset.owner_id != request.user.id and request.user.role != "ADMIN"):
            return Response({"message": "Picture not found."}, status=status.HTTP_404_NOT_FOUND)

        # Deleting a picture a post still shows would leave a broken image.
        in_use = Post.objects.filter(Q(featured_image=asset.url) | Q(content__contains=asset.url)).count()
        if in_use:
            return Response(
                {"message": f"This picture is used in {in_use} post(s). Remove it from them first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        default_storage.delete(asset.path)
        asset.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)