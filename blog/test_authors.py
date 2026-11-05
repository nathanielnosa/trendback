from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User

from .models import Post


class AuthorProfileTests(APITestCase):
    """Public author profile, and the author_username field on posts."""

    def setUp(self):
        self.author = User.objects.create_user(
            email="ada@example.com",
            username="ada",
            first_name="Ada",
            last_name="Obi",
            password="StrongPass123!",
            is_verified=True,
            role=User.Role.AUTHOR,
        )

    def publish(self, title, **overrides):
        """Create a published, public post by the author unless overridden."""
        data = dict(
            author=self.author,
            title=title,
            content="Body text.",
            status=Post.Status.PUBLISHED,
            published_at=timezone.now() - timedelta(hours=1),
        )
        data.update(overrides)
        return Post.objects.create(**data)

    def test_profile_is_public_and_counts_published_posts(self):
        self.publish("One")
        self.publish("Two")
        self.publish("Hidden draft", status=Post.Status.DRAFT)
        response = self.client.get("/api/v1/blog/authors/ada/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "ada")
        self.assertEqual(response.data["name"], "Ada Obi")
        self.assertEqual(response.data["post_count"], 2)
        self.assertEqual(response.data["id"], self.author.id)

    def test_private_details_are_not_exposed(self):
        self.publish("One")
        response = self.client.get("/api/v1/blog/authors/ada/")
        self.assertNotIn("email", response.data)
        self.assertNotIn("role", response.data)

    def test_author_without_published_posts_is_404(self):
        self.publish("Only a draft", status=Post.Status.DRAFT)
        response = self.client.get("/api/v1/blog/authors/ada/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_username_is_404(self):
        response = self.client.get("/api/v1/blog/authors/nobody/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_posts_carry_the_author_username(self):
        post = self.publish("With username")
        response = self.client.get(f"/api/v1/blog/posts/by-slug/{post.slug}/")
        self.assertEqual(response.data["author_username"], "ada")