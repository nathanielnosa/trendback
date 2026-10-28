from django.urls import path

from .views_seo import PostSEOView

urlpatterns = [
    path("posts/<slug:slug>/", PostSEOView.as_view(), name="post-seo"),
]