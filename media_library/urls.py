from django.urls import path

from .views import MediaDetailView, MediaListCreateView

urlpatterns = [
    path("", MediaListCreateView.as_view(), name="media-list"),
    path("<uuid:media_id>/", MediaDetailView.as_view(), name="media-detail"),
]