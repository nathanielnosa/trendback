from django.db.models import Q
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from paginations.pagination import MediaPagination

from . import services
from .models import Media
from .serializers import MediaSerializer, MediaUpdateSerializer, MediaUploadSerializer

UPLOAD_ROLES = {User.Role.ADMIN, User.Role.EDITOR, User.Role.AUTHOR}
MANAGE_ALL_ROLES = {User.Role.ADMIN, User.Role.EDITOR}


def can_use_library(user):
    return user.role in UPLOAD_ROLES


def can_manage_all(user):
    return user.role in MANAGE_ALL_ROLES


def forbidden():
    return Response(
        {"message": "You do not have permission to use the media library."},
        status=status.HTTP_403_FORBIDDEN,
    )


def not_found():
    return Response({"message": "Media not found."}, status=status.HTTP_404_NOT_FOUND)


def find_media(user, media_id):
    """The file, if this user may see it. Authors only see their own."""
    media = Media.objects.select_related("uploaded_by").filter(id=media_id).first()
    if media is None:
        return None
    if can_manage_all(user) or media.uploaded_by_id == user.id:
        return media
    return None



class MediaListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, *args, **kwargs):
        if not can_use_library(request.user):
            return forbidden()

        queryset = Media.objects.select_related("uploaded_by")
        if not can_manage_all(request.user) or request.query_params.get("mine") == "true":
            queryset = queryset.filter(uploaded_by=request.user)

        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(original_name__icontains=search) | Q(alt_text__icontains=search)
            )

        paginator = MediaPagination()
        page = paginator.paginate_queryset(queryset.order_by("-created_at"), request, view=self)
        data = MediaSerializer(page, many=True, context={"request": request}).data
        return paginator.get_paginated_response(data)

    def post(self, request, *args, **kwargs):
        if not can_use_library(request.user):
            return forbidden()

        serializer = MediaUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        media = services.create_media(
            request.user,
            serializer.validated_data["file"],
            serializer.validated_data.get("alt_text", ""),
        )
        return Response(
            MediaSerializer(media, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class MediaDetailView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request, media_id, *args, **kwargs):
        if not can_use_library(request.user):
            return forbidden()
        media = find_media(request.user, media_id)
        if media is None:
            return not_found()
        return Response(MediaSerializer(media, context={"request": request}).data)

    def patch(self, request, media_id, *args, **kwargs):
        if not can_use_library(request.user):
            return forbidden()
        media = find_media(request.user, media_id)
        if media is None:
            return not_found()

        serializer = MediaUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        media.alt_text = serializer.validated_data["alt_text"]
        media.save(update_fields=["alt_text"])
        return Response(MediaSerializer(media, context={"request": request}).data)

    def delete(self, request, media_id, *args, **kwargs):
        if not can_use_library(request.user):
            return forbidden()
        media = find_media(request.user, media_id)
        if media is None:
            return not_found()

        media.delete_files()
        media.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)