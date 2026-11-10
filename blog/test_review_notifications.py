from rest_framework.test import APITestCase

from accounts.models import User
from notifications.models import Notification

from .models import Post


def make_user(email, username, role):
    """Create a verified user with the given role."""
    return User.objects.create_user(
        email=email,
        username=username,
        first_name=username.title(),
        last_name="Test",
        password="StrongPass123!",
        is_verified=True,
        role=role,
    )


class ReviewNotificationTests(APITestCase):
    """Editors hear about new submissions; authors hear about the decision."""

    def setUp(self):
        self.author = make_user("a@example.com", "author1", User.Role.AUTHOR)
        self.editor = make_user("e@example.com", "editor1", User.Role.EDITOR)
        self.admin = make_user("m@example.com", "admin1", User.Role.ADMIN)
        self.other_author = make_user("o@example.com", "author2", User.Role.AUTHOR)

    def make_post(self, status):
        """Create a post by the author in the given status."""
        return Post.objects.create(author=self.author, title="My story", content="Body.", status=status)

    def test_submitting_notifies_editors_and_admins_only(self):
        post = self.make_post(Post.Status.DRAFT)
        self.client.force_authenticate(self.author)
        response = self.client.post(f"/api/v1/blog/posts/{post.id}/submit-review/", {"action": "submit"}, format="json")
        self.assertEqual(response.status_code, 200)

        recipients = set(
            Notification.objects.filter(notification_type="review_submitted").values_list("recipient__username", flat=True)
        )
        self.assertEqual(recipients, {"editor1", "admin1"})

    def test_approving_notifies_the_author(self):
        post = self.make_post(Post.Status.UNDER_REVIEW)
        self.client.force_authenticate(self.editor)
        self.client.post(f"/api/v1/blog/posts/{post.id}/review/", {"action": "approve"}, format="json")

        note = Notification.objects.get(recipient=self.author)
        self.assertEqual(note.notification_type, "post_approved")
        self.assertEqual(note.related_url, f"/studio/{post.id}/edit")

    def test_rejecting_notifies_the_author_with_the_note(self):
        post = self.make_post(Post.Status.UNDER_REVIEW)
        self.client.force_authenticate(self.editor)
        self.client.post(
            f"/api/v1/blog/posts/{post.id}/review/",
            {"action": "reject", "review_notes": "Add a source."},
            format="json",
        )

        note = Notification.objects.get(recipient=self.author)
        self.assertEqual(note.notification_type, "post_rejected")
        self.assertIn("Add a source.", note.message)

    def test_reviewing_a_post_not_under_review_is_a_clean_400(self):
        post = self.make_post(Post.Status.DRAFT)
        self.client.force_authenticate(self.editor)
        response = self.client.post(f"/api/v1/blog/posts/{post.id}/review/", {"action": "approve"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["message"], "Only posts under review can be reviewed.")
        self.assertEqual(Notification.objects.count(), 0)