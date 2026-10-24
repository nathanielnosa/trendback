from datetime import timedelta

from django.urls import reverse, NoReverseMatch
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from .models import Post


def url(name, **kwargs):
    """Reverse a URL, with or without the /api/<version>/ kwarg."""
    try:
        return reverse(name, kwargs={"version": "v1", **kwargs})
    except NoReverseMatch:
        return reverse(name, kwargs=kwargs)


class DashboardTestBase(APITestCase):
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

    def make_post(self, author, title="A post", state=Post.Status.DRAFT, **kwargs):
        return Post.objects.create(
            author=author, title=title, content="Body", status=state, **kwargs
        )

    def set_updated(self, post, days_ago):
        Post.objects.filter(pk=post.pk).update(
            updated_at=timezone.now() - timedelta(days=days_ago)
        )

    def titles(self, response):
        return [p["title"] for p in response.data["results"]]

    def setUp(self):
        self.admin = self.make_user(User.Role.ADMIN, "admin1")
        self.editor = self.make_user(User.Role.EDITOR, "editor1")
        self.author = self.make_user(User.Role.AUTHOR, "author1")
        self.other_author = self.make_user(User.Role.AUTHOR, "author2")
        self.contributor = self.make_user(User.Role.CONTRIBUTOR, "contrib1")
        self.subscriber = self.make_user(User.Role.SUBSCRIBER, "reader1")


# ============================================================
# MY POSTS
# ============================================================
class MyPostsTests(DashboardTestBase):
    def setUp(self):
        super().setUp()
        self.my_posts_url = url("my-posts")

    def test_anonymous_gets_401(self):
        response = self.client.get(self.my_posts_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_subscriber_gets_403(self):
        self.client.force_authenticate(user=self.subscriber)
        response = self.client.get(self.my_posts_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_author_sees_own_posts_in_every_status(self):
        for index, state in enumerate(Post.Status.values):
            self.make_post(self.author, f"Post {index}", state=state)
        self.client.force_authenticate(user=self.author)

        response = self.client.get(self.my_posts_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], len(Post.Status.values))

    def test_other_peoples_posts_are_excluded(self):
        self.make_post(self.author, "Mine")
        self.make_post(self.other_author, "Theirs")
        self.client.force_authenticate(user=self.author)
        self.assertEqual(self.titles(self.client.get(self.my_posts_url)), ["Mine"])

    def test_editor_sees_only_their_own_posts_here(self):
        self.make_post(self.editor, "Editor post")
        self.make_post(self.author, "Author post")
        self.client.force_authenticate(user=self.editor)
        self.assertEqual(
            self.titles(self.client.get(self.my_posts_url)), ["Editor post"]
        )

    def test_contributor_can_use_it(self):
        self.make_post(self.contributor, "Contributor post")
        self.client.force_authenticate(user=self.contributor)
        response = self.client.get(self.my_posts_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.titles(response), ["Contributor post"])

    def test_author_sees_review_notes_on_own_post(self):
        self.make_post(self.author, "Rejected", review_notes="Add sources please")
        self.client.force_authenticate(user=self.author)
        item = self.client.get(self.my_posts_url).data["results"][0]
        self.assertEqual(item["review_notes"], "Add sources please")

    def test_filter_by_status(self):
        self.make_post(self.author, "Draft", state=Post.Status.DRAFT)
        self.make_post(self.author, "Live", state=Post.Status.PUBLISHED)
        self.client.force_authenticate(user=self.author)

        response = self.client.get(self.my_posts_url, {"status": "published"})

        self.assertEqual(self.titles(response), ["Live"])

    def test_invalid_status_is_400(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.get(self.my_posts_url, {"status": "bogus"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_search_by_title(self):
        self.make_post(self.author, "Python tips")
        self.make_post(self.author, "Cooking")
        self.client.force_authenticate(user=self.author)
        response = self.client.get(self.my_posts_url, {"search": "python"})
        self.assertEqual(self.titles(response), ["Python tips"])

    def test_most_recently_updated_first(self):
        old = self.make_post(self.author, "Old")
        new = self.make_post(self.author, "New")
        self.set_updated(old, days_ago=5)
        self.set_updated(new, days_ago=0)
        self.client.force_authenticate(user=self.author)
        self.assertEqual(self.titles(self.client.get(self.my_posts_url)), ["New", "Old"])

    def test_has_pagination_envelope(self):
        self.make_post(self.author)
        self.client.force_authenticate(user=self.author)
        response = self.client.get(self.my_posts_url)
        for key in ("count", "next", "previous", "results"):
            self.assertIn(key, response.data)

    def test_second_page(self):
        for index in range(12):
            self.make_post(self.author, f"Post {index}")
        self.client.force_authenticate(user=self.author)
        response = self.client.get(self.my_posts_url, {"page": 2})
        self.assertEqual(len(response.data["results"]), 2)


# ============================================================
# REVIEW QUEUE
# ============================================================
class ReviewQueueTests(DashboardTestBase):
    def setUp(self):
        super().setUp()
        self.queue_url = url("review-queue")

    def test_anonymous_gets_401(self):
        response = self.client.get(self.queue_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_writers_and_readers_get_403(self):
        for user in (self.author, self.contributor, self.subscriber):
            with self.subTest(role=user.role):
                self.client.force_authenticate(user=user)
                response = self.client.get(self.queue_url)
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_editor_and_admin_can_view(self):
        for user in (self.editor, self.admin):
            with self.subTest(role=user.role):
                self.client.force_authenticate(user=user)
                response = self.client.get(self.queue_url)
                self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_default_shows_only_posts_under_review(self):
        self.make_post(self.author, "Waiting", state=Post.Status.UNDER_REVIEW)
        self.make_post(self.author, "Draft", state=Post.Status.DRAFT)
        self.make_post(self.author, "Approved", state=Post.Status.APPROVED)
        self.make_post(self.author, "Live", state=Post.Status.PUBLISHED)
        self.client.force_authenticate(user=self.editor)

        self.assertEqual(self.titles(self.client.get(self.queue_url)), ["Waiting"])

    def test_includes_posts_from_every_author(self):
        self.make_post(self.author, "A", state=Post.Status.UNDER_REVIEW)
        self.make_post(self.other_author, "B", state=Post.Status.UNDER_REVIEW)
        self.client.force_authenticate(user=self.editor)
        self.assertEqual(self.client.get(self.queue_url).data["count"], 2)

    def test_oldest_waiting_first(self):
        new = self.make_post(self.author, "New", state=Post.Status.UNDER_REVIEW)
        old = self.make_post(self.author, "Old", state=Post.Status.UNDER_REVIEW)
        self.set_updated(old, days_ago=3)
        self.set_updated(new, days_ago=0)
        self.client.force_authenticate(user=self.editor)
        self.assertEqual(self.titles(self.client.get(self.queue_url)), ["Old", "New"])

    def test_approved_posts_waiting_to_be_published(self):
        self.make_post(self.author, "Waiting", state=Post.Status.UNDER_REVIEW)
        self.make_post(self.author, "Ready", state=Post.Status.APPROVED)
        self.client.force_authenticate(user=self.editor)
        response = self.client.get(self.queue_url, {"status": "approved"})
        self.assertEqual(self.titles(response), ["Ready"])

    def test_other_statuses_are_rejected(self):
        self.client.force_authenticate(user=self.editor)
        for value in ("draft", "published", "bogus"):
            with self.subTest(status=value):
                response = self.client.get(self.queue_url, {"status": value})
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_has_pagination_envelope(self):
        self.make_post(self.author, state=Post.Status.UNDER_REVIEW)
        self.client.force_authenticate(user=self.editor)
        response = self.client.get(self.queue_url)
        for key in ("count", "next", "previous", "results"):
            self.assertIn(key, response.data)

    def test_item_shows_the_author(self):
        self.make_post(self.author, "Waiting", state=Post.Status.UNDER_REVIEW)
        self.client.force_authenticate(user=self.editor)
        item = self.client.get(self.queue_url).data["results"][0]
        self.assertEqual(item["author"], self.author.id)
        self.assertEqual(item["author_name"], "Author1 Tester")

    def test_approving_removes_a_post_from_the_queue(self):
        post = self.make_post(self.author, "Waiting", state=Post.Status.UNDER_REVIEW)
        self.client.force_authenticate(user=self.editor)
        self.client.post(
            url("post-review", post_id=post.id), {"action": "approve"}, format="json"
        )
        self.assertEqual(self.client.get(self.queue_url).data["count"], 0)