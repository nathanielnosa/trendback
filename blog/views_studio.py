import uuid

from django.core.files.storage import default_storage
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import CanCreatePost

from .models import Post
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
class MediaUploadView(APIView):
    """Upload one picture; answers with its full address to use in a post."""

    permission_classes = [CanCreatePost]
    parser_classes = [MultiPartParser, FormParser]

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

        return Response(
            {"url": url, "name": saved, "size": upload.size},
            status=status.HTTP_201_CREATED,
        )