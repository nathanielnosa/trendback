from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import User

from .models import Post


class PublishScheduledTests(TestCase):
    """The scheduler command only publishes approved posts whose time has come."""

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

    def make(self, title, status, scheduled_at):
        """Create a post with the given status and scheduled time."""
        return Post.objects.create(
            author=self.author,
            title=title,
            content="Body.",
            status=status,
            scheduled_at=scheduled_at,
        )

    def run_command(self):
        call_command("publish_scheduled", stdout=StringIO())

    def test_due_post_is_published(self):
        post = self.make("Due", Post.Status.APPROVED, timezone.now() - timedelta(minutes=1))
        self.run_command()
        post.refresh_from_db()
        self.assertEqual(post.status, Post.Status.PUBLISHED)
        self.assertIsNotNone(post.published_at)
        self.assertIsNone(post.scheduled_at)

    def test_future_post_is_left_alone(self):
        post = self.make("Later", Post.Status.APPROVED, timezone.now() + timedelta(hours=2))
        self.run_command()
        post.refresh_from_db()
        self.assertEqual(post.status, Post.Status.APPROVED)

    def test_draft_with_a_past_time_is_left_alone(self):
        post = self.make("Draft", Post.Status.DRAFT, timezone.now() - timedelta(minutes=5))
        self.run_command()
        post.refresh_from_db()
        self.assertEqual(post.status, Post.Status.DRAFT)

    def test_running_twice_publishes_once(self):
        post = self.make("Once", Post.Status.APPROVED, timezone.now() - timedelta(minutes=1))
        self.run_command()
        first = Post.objects.get(pk=post.pk).published_at
        self.run_command()
        self.assertEqual(Post.objects.get(pk=post.pk).published_at, first)