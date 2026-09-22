from django.urls import path

from .views import (
    CommentListCreateView,
    CommentDetailView,
    CommentModerationView
)

urlpatterns = [
    path("",CommentListCreateView.as_view(),name="comment-list-create"),
    path("<uuid:comment_id>/",CommentDetailView.as_view(),name="comment-detail"),
    path("<uuid:comment_id>/moderate/",CommentModerationView.as_view(),name="comment-moderate"),
]