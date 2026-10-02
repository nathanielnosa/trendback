from django.urls import path

from .views import(
     PostReactionView,
     PostBookmarkView,
    BookmarkListView,
     )


urlpatterns = [
    path("posts/<uuid:post_id>/reaction/",PostReactionView.as_view(),name="post-reaction"),
    path("posts/<uuid:post_id>/bookmark/",PostBookmarkView.as_view(),name="post-bookmark"),
    path("bookmarks/",BookmarkListView.as_view(),name="bookmark-list"),
]