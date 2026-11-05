from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from analytics.models import AnalyticsEvent

from .models import Post


class PostBySlugTests(APITestCase):
    """The public endpoint the frontend post page uses: /blog/posts/by-slug/<slug>/."""

    def setUp(self):
        self.author = User.objects.create_user(
            email="writer@example.com",
            username="writer",
            first_name="Wri",
            last_name="Ter",
            password="StrongPass123!",
            is_verified=True,
            role=User.Role.AUTHOR,
        )

    def make_post(self, title, **overrides):
        """Create a post that is published and public unless overridden."""
        data = dict(
            author=self.author,
            title=title,
            content="Some body text for the story.",
            status=Post.Status.PUBLISHED,
            published_at=timezone.now() - timedelta(hours=1),
        )
        data.update(overrides)
        return Post.objects.create(**data)

    def url(self, slug):
        return f"/api/v1/blog/posts/by-slug/{slug}/"

    def test_published_post_is_returned_to_anonymous_visitors(self):
        post = self.make_post("Hello Slug World")
        response = self.client.get(self.url(post.slug))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], post.slug)
        self.assertEqual(response.data["title"], "Hello Slug World")

    def test_draft_post_is_hidden(self):
        post = self.make_post("Secret Draft", status=Post.Status.DRAFT)
        response = self.client.get(self.url(post.slug))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_non_public_post_is_hidden(self):
        # Any visibility other than PUBLIC must not be served.
        other = [v for v, _ in Post.Visibility.choices if v != Post.Visibility.PUBLIC]
        if not other:
            self.skipTest("Post has only one visibility value.")
        post = self.make_post("Members Only", visibility=other[0])
        response = self.client.get(self.url(post.slug))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_slug_returns_404_with_message(self):
        response = self.client.get(self.url("no-such-post"))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["message"], "Post not found.")

    def test_a_view_event_is_recorded(self):
        post = self.make_post("Counted Story")
        before = AnalyticsEvent.objects.filter(
            event_type=AnalyticsEvent.EventType.POST_VIEW, post=post
        ).count()
        self.client.get(self.url(post.slug))
        after = AnalyticsEvent.objects.filter(
            event_type=AnalyticsEvent.EventType.POST_VIEW, post=post
        ).count()
        self.assertEqual(after, before + 1)