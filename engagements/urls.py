from django.urls import path

from .views import(
     PostReactionView,
     PostBookmarkView,
    BookmarkListView,
    PostShareView
     )


urlpatterns = [
    path("posts/<uuid:post_id>/reaction/",PostReactionView.as_view(),name="post-reaction"),
    path("posts/<uuid:post_id>/bookmark/",PostBookmarkView.as_view(),name="post-bookmark"),
    path("bookmarks/",BookmarkListView.as_view(),name="bookmark-list"),
    path("posts/<uuid:post_id>/share/",PostShareView.as_view(),name="post-share"),
]