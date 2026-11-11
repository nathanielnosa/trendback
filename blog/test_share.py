from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User

from .models import Post


@override_settings(FRONTEND_URL="https://trendarchive.example", SITE_NAME="Trend Test")
class SharePreviewTests(TestCase):
    """Link robots get the right tags; hidden posts never leak."""

    def setUp(self):
        self.author = User.objects.create_user(
            email="writer@example.com",
            username="writer",
            first_name="Ada",
            last_name="Obi",
            password="StrongPass123!",
            is_verified=True,
            role=User.Role.AUTHOR,
        )

    def make(self, title, **extra):
        """Create a published public post, with any fields overridden."""
        fields = dict(
            author=self.author,
            title=title,
            content="<p>Hello <b>world</b> of music.</p>",
            status=Post.Status.PUBLISHED,
            visibility=Post.Visibility.PUBLIC,
            published_at=timezone.now() - timedelta(hours=1),
        )
        fields.update(extra)
        return Post.objects.create(**fields)

    def test_share_page_has_preview_tags(self):
        post = self.make("Big \"Release\" & more", featured_image="https://cdn.example/pic.jpg")
        response = self.client.get(f"/share/posts/{post.slug}/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('property="og:title" content="Big &quot;Release&quot; &amp; more"', html)
        self.assertIn('property="og:image" content="https://cdn.example/pic.jpg"', html)
        self.assertIn('name="twitter:card" content="summary_large_image"', html)
        self.assertIn(f"https://trendarchive.example/posts/{post.slug}", html)
        self.assertIn("Hello world of music.", html)

    def test_without_a_picture_the_card_is_small(self):
        post = self.make("No picture")
        html = self.client.get(f"/share/posts/{post.slug}/").content.decode()
        self.assertIn('name="twitter:card" content="summary"', html)
        self.assertNotIn("og:image", html)

    def test_draft_and_private_posts_are_not_found(self):
        draft = self.make("Draft", status=Post.Status.DRAFT)
        private = self.make("Private", visibility=Post.Visibility.PRIVATE)
        self.assertEqual(self.client.get(f"/share/posts/{draft.slug}/").status_code, 404)
        self.assertEqual(self.client.get(f"/share/posts/{private.slug}/").status_code, 404)

