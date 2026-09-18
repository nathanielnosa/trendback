from django.urls import path

from .views import (
    PostListCreateView,
    PostDetailView,
    CategoryListCreateView,
    CategoryDetailView,
    TagListCreateView,
    TagDetailView,
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
]