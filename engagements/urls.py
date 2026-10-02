from django.urls import path

from .views import PostReactionView


urlpatterns = [
    path("posts/<uuid:post_id>/reaction/",PostReactionView.as_view(),name="post-reaction"),
]