from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User

from .models import Post


class LightListTests(APITestCase):
    """Lists leave out the full article text; the single-post endpoint keeps it."""

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
        self.post = Post.objects.create(
            author=self.author,
            title="Long story",
            content="<p>The full article body.</p>",
            status=Post.Status.PUBLISHED,
            visibility=Post.Visibility.PUBLIC,
            published_at=timezone.now(),
        )

    def test_public_list_has_no_content(self):
        response = self.client.get("/api/v1/blog/posts/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertNotIn("content", response.data["results"][0])
        self.assertEqual(response.data["results"][0]["title"], "Long story")

    def test_my_posts_list_has_no_content(self):
        self.client.force_authenticate(self.author)
        response = self.client.get("/api/v1/blog/my-posts/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("content", response.data["results"][0])

    def test_single_post_keeps_its_content(self):
        response = self.client.get(f"/api/v1/blog/posts/by-slug/{self.post.slug}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["content"], "<p>The full article body.</p>")