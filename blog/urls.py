from django.urls import path

from .views import (
    PostListCreateView,
    PostDetailView,
    CategoryListCreateView,
    CategoryDetailView,
    TagListCreateView,
    TagDetailView,
    PostReviewView,
    PostPublishView,
    PostSubmitReviewView
)


urlpatterns = [

    # POSTS
    path("posts/",PostListCreateView.as_view(),name="post-list-create"),
    path("posts/<uuid:post_id>/",PostDetailView.as_view(),name="post-detail"),

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
]