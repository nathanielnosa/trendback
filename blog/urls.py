from django.urls import path

from .views import (
    PostListCreateView,
    PostDetailView,
    PostBySlugView,
    CategoryListCreateView,
    CategoryDetailView,
    TagListCreateView,
    TagDetailView,
    PostReviewView,
    PostPublishView,
    PostSubmitReviewView
)
from .views_dashboard import MyPostsView, ReviewQueueView
from .views_authors import AuthorProfileView
from .views_studio import MediaUploadView, MyPostDetailView

urlpatterns = [

    # POSTS
    path("posts/",PostListCreateView.as_view(),name="post-list-create"),
    path("posts/by-slug/<slug:slug>/", PostBySlugView.as_view(), name="post-by-slug"),
    path("posts/<uuid:post_id>/",PostDetailView.as_view(),name="post-detail"),

    # DASHBOARD
    path("my-posts/",MyPostsView.as_view(),name="my-posts"),
    path("review-queue/",ReviewQueueView.as_view(),name="review-queue"),
    path("my-posts/<uuid:post_id>/", MyPostDetailView.as_view(), name="my-post-detail"),
    path("media/", MediaUploadView.as_view(), name="media-upload"),
    
    # CATEGORIES
    path("categories/",CategoryListCreateView.as_view(),name="category-list-create"),
    path("categories/<uuid:category_id>/",CategoryDetailView.as_view(),name="category-detail"),

    # TAGS
    path("tags/",TagListCreateView.as_view(),name="tag-list-create"),
    path("tags/<uuid:tag_id>/",TagDetailView.as_view(),name="tag-detail"),

    # REVIEW
    path("posts/<uuid:post_id>/review/",PostReviewView.as_view(),name="post-review"),
    
    # PUBLISH
    path("posts/<uuid:post_id>/publish/",PostPublishView.as_view(),name="post-publish"),
    path(
    "posts/<uuid:post_id>/submit-review/",PostSubmitReviewView.as_view(),name="post-submit-review"
),
    # AUTHOR
    path("authors/<str:username>/", AuthorProfileView.as_view(), name="author-profile"),
]