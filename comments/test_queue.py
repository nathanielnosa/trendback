from datetime import timedelta

from django.urls import reverse, NoReverseMatch
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from blog.models import Post

from .models import Comment

PENDING = Comment.Status.PENDING


def url(name, **kwargs):
    """Reverse a URL, with or without the /api/<version>/ kwarg."""
    try:
        return reverse(name, kwargs={"version": "v1", **kwargs})
    except NoReverseMatch:
        return reverse(name, kwargs=kwargs)


class PendingCommentsTests(APITestCase):
    def make_user(self, role, username):
        return User.objects.create_user(
            email=f"{username}@example.com",
            username=username,
            first_name=username.title(),
            last_name="Tester",
            password="StrongPass123!",
            is_verified=True,
            role=role,
        )

    def make_post(self, author, title):
        return Post.objects.create(
            author=author, title=title, content="Body", status=Post.Status.PUBLISHED
        )

    def make_comment(self, post, content="Nice", state=PENDING, days_ago=0):
        comment = Comment.objects.create(
            post=post, author=self.reader, content=content, status=state
        )
        if days_ago:
            Comment.objects.filter(pk=comment.pk).update(
                created_at=timezone.now() - timedelta(days=days_ago)
            )
        return comment

    def contents(self, response):
        return [c["content"] for c in response.data["results"]]

    def setUp(self):
        self.admin = self.make_user(User.Role.ADMIN, "admin1")
        self.editor = self.make_user(User.Role.EDITOR, "editor1")
        self.author = self.make_user(User.Role.AUTHOR, "author1")
        self.other_author = self.make_user(User.Role.AUTHOR, "author2")
        self.contributor = self.make_user(User.Role.CONTRIBUTOR, "contrib1")
        self.reader = self.make_user(User.Role.SUBSCRIBER, "reader1")

        self.post = self.make_post(self.author, "Author one post")
        self.other_post = self.make_post(self.other_author, "Author two post")
        self.pending_url = url("comment-pending")

    def test_anonymous_gets_401(self):
        response = self.client.get(self.pending_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_readers_and_contributors_get_403(self):
        for user in (self.reader, self.contributor):
            with self.subTest(role=user.role):
                self.client.force_authenticate(user=user)
                response = self.client.get(self.pending_url)
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_editor_and_admin_see_all_pending_comments(self):
        self.make_comment(self.post, "on one")
        self.make_comment(self.other_post, "on two")
        for user in (self.editor, self.admin):
            with self.subTest(role=user.role):
                self.client.force_authenticate(user=user)
                response = self.client.get(self.pending_url)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data["count"], 2)

    def test_only_pending_comments_are_listed(self):
        self.make_comment(self.post, "pending", state=PENDING)
        self.make_comment(self.post, "approved", state=Comment.Status.APPROVED)
        self.make_comment(self.post, "rejected", state=Comment.Status.REJECTED)
        self.make_comment(self.post, "deleted", state=Comment.Status.DELETED)
        self.client.force_authenticate(user=self.editor)
        self.assertEqual(self.contents(self.client.get(self.pending_url)), ["pending"])

    def test_author_sees_only_comments_on_their_own_posts(self):
        self.make_comment(self.post, "on mine")
        self.make_comment(self.other_post, "on theirs")
        self.client.force_authenticate(user=self.author)
        self.assertEqual(self.contents(self.client.get(self.pending_url)), ["on mine"])

    def test_author_with_no_posts_commented_on_sees_nothing(self):
        self.make_comment(self.post, "on author one")
        self.client.force_authenticate(user=self.other_author)
        # author two has one pending comment of their own; author one's is hidden
        self.assertEqual(self.client.get(self.pending_url).data["count"], 0)

    def test_oldest_first(self):
        self.make_comment(self.post, "newer", days_ago=0)
        self.make_comment(self.post, "older", days_ago=3)
        self.client.force_authenticate(user=self.editor)
        self.assertEqual(
            self.contents(self.client.get(self.pending_url)), ["older", "newer"]
        )

    def test_item_shows_post_title_and_author(self):
        self.make_comment(self.post, "hello")
        self.client.force_authenticate(user=self.editor)
        item = self.client.get(self.pending_url).data["results"][0]
        self.assertEqual(item["post_title"], "Author one post")
        self.assertEqual(item["author_name"], "Reader1 Tester")
        self.assertEqual(item["status"], "pending")

    def test_has_pagination_envelope(self):
        self.make_comment(self.post)
        self.client.force_authenticate(user=self.editor)
        response = self.client.get(self.pending_url)
        for key in ("count", "next", "previous", "results"):
            self.assertIn(key, response.data)

    def test_second_page(self):
        for index in range(22):
            self.make_comment(self.post, f"c{index}")
        self.client.force_authenticate(user=self.editor)
        response = self.client.get(self.pending_url, {"page": 2})
        self.assertEqual(len(response.data["results"]), 2)

    def test_approving_removes_a_comment_from_the_queue(self):
        comment = self.make_comment(self.post)
        self.client.force_authenticate(user=self.editor)
        self.client.post(
            url("comment-moderate", comment_id=comment.id),
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(self.client.get(self.pending_url).data["count"], 0)

    def test_queue_items_can_be_moderated_by_the_post_owner(self):
        comment = self.make_comment(self.post)
        self.client.force_authenticate(user=self.author)
        listed = self.client.get(self.pending_url).data["results"][0]
        response = self.client.post(
            url("comment-moderate", comment_id=listed["id"]),
            {"action": "reject"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        comment.refresh_from_db()
        self.assertEqual(comment.status, Comment.Status.REJECTED)