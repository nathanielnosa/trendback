import uuid
from datetime import timedelta

from django.urls import reverse, NoReverseMatch
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from .models import Post, Category, Tag
from django.test import override_settings


# ============================================================
# HELPERS
# ============================================================
def url(name, **kwargs):
    """Reverse a URL, with or without the /api/<version>/ kwarg."""
    try:
        return reverse(name, kwargs={"version": "v1", **kwargs})
    except NoReverseMatch:
        return reverse(name, kwargs=kwargs)


def results(response):
    """List data, with or without a pagination envelope."""
    data = response.data
    return data["results"] if isinstance(data, dict) and "results" in data else data

@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]
)
class BlogTestBase(APITestCase):
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

    def make_post(self, author, title="A post", **kwargs):
        return Post.objects.create(
            author=author, title=title, content="Some content", **kwargs
        )

    def setUp(self):
        self.admin = self.make_user(User.Role.ADMIN, "admin1")
        self.editor = self.make_user(User.Role.EDITOR, "editor1")
        self.author = self.make_user(User.Role.AUTHOR, "author1")
        self.other_author = self.make_user(User.Role.AUTHOR, "author2")
        self.contributor = self.make_user(User.Role.CONTRIBUTOR, "contrib1")
        self.subscriber = self.make_user(User.Role.SUBSCRIBER, "reader1")


# ============================================================
# MODEL TESTS
# ============================================================
class PostModelTests(BlogTestBase):
    def test_slug_is_generated_from_title(self):
        post = self.make_post(self.author, title="Hello World")
        self.assertEqual(post.slug, "hello-world")

    def test_duplicate_titles_get_unique_slugs(self):
        first = self.make_post(self.author, title="Same Title")
        second = self.make_post(self.author, title="Same Title")
        self.assertNotEqual(first.slug, second.slug)
        self.assertEqual(second.slug, "same-title-1")

    def test_new_post_defaults_to_public_draft(self):
        post = self.make_post(self.author)
        self.assertEqual(post.status, Post.Status.DRAFT)
        self.assertEqual(post.visibility, Post.Visibility.PUBLIC)
        self.assertFalse(post.is_public())

    def test_published_public_post_is_public(self):
        post = self.make_post(self.author, status=Post.Status.PUBLISHED)
        self.assertTrue(post.is_public())

    def test_deleting_category_keeps_posts(self):
        category = Category.objects.create(name="News", slug="news")
        post = self.make_post(self.author, category=category)
        category.delete()
        post.refresh_from_db()
        self.assertIsNone(post.category)


# ============================================================
# PUBLIC READS
# ============================================================
class PublicPostReadTests(BlogTestBase):
    def test_list_shows_only_published_public_posts(self):
        self.make_post(self.author, "Live", status=Post.Status.PUBLISHED)
        self.make_post(self.author, "Draft", status=Post.Status.DRAFT)
        self.make_post(self.author, "Review", status=Post.Status.UNDER_REVIEW)
        self.make_post(
            self.author,
            "Private",
            status=Post.Status.PUBLISHED,
            visibility=Post.Visibility.PRIVATE,
        )

        response = self.client.get(url("post-list-create"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [p["title"] for p in results(response)]
        self.assertEqual(titles, ["Live"])

    def test_list_has_pagination_envelope(self):
        self.make_post(self.author, status=Post.Status.PUBLISHED)
        response = self.client.get(url("post-list-create"))
        for key in ("count", "next", "previous", "results"):
            self.assertIn(key, response.data)

    def test_list_filters_by_category_slug(self):
        news = Category.objects.create(name="News", slug="news")
        tech = Category.objects.create(name="Tech", slug="tech")
        self.make_post(self.author, "N", status=Post.Status.PUBLISHED, category=news)
        self.make_post(self.author, "T", status=Post.Status.PUBLISHED, category=tech)

        response = self.client.get(url("post-list-create"), {"category": "news"})
        self.assertEqual([p["title"] for p in results(response)], ["N"])

    def test_list_filters_by_tag_slug(self):
        tag = Tag.objects.create(name="Django", slug="django")
        tagged = self.make_post(self.author, "Tagged", status=Post.Status.PUBLISHED)
        tagged.tags.add(tag)
        self.make_post(self.author, "Plain", status=Post.Status.PUBLISHED)

        response = self.client.get(url("post-list-create"), {"tag": "django"})
        self.assertEqual([p["title"] for p in results(response)], ["Tagged"])

    def test_list_search_matches_title(self):
        self.make_post(self.author, "Python tips", status=Post.Status.PUBLISHED)
        self.make_post(self.author, "Cooking", status=Post.Status.PUBLISHED)

        response = self.client.get(url("post-list-create"), {"search": "python"})
        self.assertEqual([p["title"] for p in results(response)], ["Python tips"])

    def test_list_filters_by_featured(self):
        self.make_post(
            self.author, "Star", status=Post.Status.PUBLISHED, is_featured=True
        )
        self.make_post(self.author, "Normal", status=Post.Status.PUBLISHED)

        response = self.client.get(url("post-list-create"), {"featured": "true"})
        self.assertEqual([p["title"] for p in results(response)], ["Star"])

    def test_list_filters_by_author(self):
        self.make_post(self.author, "Mine", status=Post.Status.PUBLISHED)
        self.make_post(self.other_author, "Theirs", status=Post.Status.PUBLISHED)

        response = self.client.get(
            url("post-list-create"), {"author": str(self.author.id)}
        )
        self.assertEqual([p["title"] for p in results(response)], ["Mine"])

    def test_detail_returns_published_post(self):
        post = self.make_post(self.author, status=Post.Status.PUBLISHED)
        response = self.client.get(url("post-detail", post_id=post.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], post.title)

    def test_detail_hides_draft_post(self):
        post = self.make_post(self.author, status=Post.Status.DRAFT)
        response = self.client.get(url("post-detail", post_id=post.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_detail_hides_private_post(self):
        post = self.make_post(
            self.author,
            status=Post.Status.PUBLISHED,
            visibility=Post.Visibility.PRIVATE,
        )
        response = self.client.get(url("post-detail", post_id=post.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_detail_unknown_id_is_404(self):
        response = self.client.get(url("post-detail", post_id=uuid.uuid4()))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ============================================================
# CREATE
# ============================================================
class PostCreateTests(BlogTestBase):
    def payload(self, **overrides):
        data = {"title": "New post", "content": "Body text"}
        data.update(overrides)
        return data

    def test_anonymous_cannot_create(self):
        response = self.client.post(
            url("post-list-create"), self.payload(), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_subscriber_cannot_create(self):
        self.client.force_authenticate(user=self.subscriber)
        response = self.client.post(
            url("post-list-create"), self.payload(), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_author_can_create_draft_and_becomes_author(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.post(
            url("post-list-create"), self.payload(), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        post = Post.objects.get(title="New post")
        self.assertEqual(post.author, self.author)
        self.assertEqual(post.status, Post.Status.DRAFT)

    def test_contributor_can_create_draft(self):
        self.client.force_authenticate(user=self.contributor)
        response = self.client.post(
            url("post-list-create"), self.payload(), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_author_cannot_choose_another_author(self):
        self.client.force_authenticate(user=self.author)
        self.client.post(
            url("post-list-create"),
            self.payload(author=self.other_author.id),
            format="json",
        )
        post = Post.objects.get(title="New post")
        self.assertEqual(post.author, self.author)

    def test_author_cannot_create_published_post(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.post(
            url("post-list-create"),
            self.payload(status=Post.Status.PUBLISHED),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Post.objects.filter(title="New post").exists())

    def test_contributor_cannot_create_published_post(self):
        self.client.force_authenticate(user=self.contributor)
        response = self.client.post(
            url("post-list-create"),
            self.payload(status=Post.Status.PUBLISHED),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_requires_title_and_content(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.post(url("post-list-create"), {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", response.data)
        self.assertIn("content", response.data)

    def test_create_rejects_bad_featured_image_url(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.post(
            url("post-list-create"),
            self.payload(featured_image="not-a-url"),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_with_category_and_tags(self):
        category = Category.objects.create(name="News", slug="news")
        tag = Tag.objects.create(name="Django", slug="django")
        self.client.force_authenticate(user=self.author)
        response = self.client.post(
            url("post-list-create"),
            self.payload(category=str(category.id), tags=[str(tag.id)]),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        post = Post.objects.get(title="New post")
        self.assertEqual(post.category, category)
        self.assertEqual(list(post.tags.all()), [tag])


# ============================================================
# EDIT / DELETE PERMISSIONS
# ============================================================
class PostEditDeleteTests(BlogTestBase):
    def setUp(self):
        super().setUp()
        self.post = self.make_post(self.author, "Original", status=Post.Status.DRAFT)
        self.detail = url("post-detail", post_id=self.post.id)

    # ----- edit -----
    def test_anonymous_cannot_edit(self):
        response = self.client.patch(self.detail, {"title": "X"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_subscriber_cannot_edit(self):
        self.client.force_authenticate(user=self.subscriber)
        response = self.client.patch(self.detail, {"title": "X"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_edit(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.patch(self.detail, {"title": "Changed"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, "Changed")

    def test_non_owner_author_cannot_edit(self):
        self.client.force_authenticate(user=self.other_author)
        response = self.client.patch(self.detail, {"title": "Hacked"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, "Original")

    def test_editor_can_edit_any_post(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.patch(self.detail, {"title": "By editor"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_can_edit_any_post(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.patch(self.detail, {"title": "By admin"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_put_replaces_post(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.put(
            self.detail, {"title": "Full", "content": "New body"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.post.refresh_from_db()
        self.assertEqual(self.post.content, "New body")

    def test_edit_unknown_post_is_404(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.patch(
            url("post-detail", post_id=uuid.uuid4()), {"title": "X"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_author_cannot_publish_own_draft_via_patch(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.patch(
            self.detail, {"status": Post.Status.PUBLISHED}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, Post.Status.DRAFT)

    def test_edit_cannot_change_author_or_slug(self):
        self.client.force_authenticate(user=self.author)
        self.client.patch(
            self.detail,
            {"author": str(self.other_author.id), "slug": "hijacked"},
            format="json",
        )
        self.post.refresh_from_db()
        self.assertEqual(self.post.author, self.author)
        self.assertEqual(self.post.slug, "original")

    # ----- delete -----
    def test_anonymous_cannot_delete(self):
        response = self.client.delete(self.detail)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_subscriber_cannot_delete(self):
        self.client.force_authenticate(user=self.subscriber)
        response = self.client.delete(self.detail)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_owner_author_cannot_delete(self):
        self.client.force_authenticate(user=self.other_author)
        response = self.client.delete(self.detail)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Post.objects.filter(id=self.post.id).exists())

    def test_owner_can_delete(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.delete(self.detail)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Post.objects.filter(id=self.post.id).exists())

    def test_editor_can_delete_any_post(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.delete(self.detail)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_unknown_post_is_404(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.delete(url("post-detail", post_id=uuid.uuid4()))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ============================================================
# SUBMIT FOR REVIEW
# ============================================================
class PostSubmitReviewTests(BlogTestBase):
    def setUp(self):
        super().setUp()
        self.post = self.make_post(self.author, status=Post.Status.DRAFT)
        self.submit_url = url("post-submit-review", post_id=self.post.id)

    def test_anonymous_cannot_submit(self):
        response = self.client.post(
            self.submit_url, {"action": "submit"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_owner_can_submit_draft(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.post(
            self.submit_url, {"action": "submit"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, Post.Status.UNDER_REVIEW)

    def test_non_owner_cannot_submit(self):
        self.client.force_authenticate(user=self.other_author)
        response = self.client.post(
            self.submit_url, {"action": "submit"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, Post.Status.DRAFT)

    def test_cannot_submit_non_draft(self):
        self.post.status = Post.Status.UNDER_REVIEW
        self.post.save()
        self.client.force_authenticate(user=self.author)
        response = self.client.post(
            self.submit_url, {"action": "submit"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_submit_requires_valid_action(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.post(self.submit_url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_submit_unknown_post_is_404(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.post(
            url("post-submit-review", post_id=uuid.uuid4()),
            {"action": "submit"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ============================================================
# REVIEW (approve / reject)
# ============================================================
class PostReviewTests(BlogTestBase):
    def setUp(self):
        super().setUp()
        self.post = self.make_post(self.author, status=Post.Status.UNDER_REVIEW)
        self.review_url = url("post-review", post_id=self.post.id)

    def test_anonymous_cannot_review(self):
        response = self.client.post(
            self.review_url, {"action": "approve"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_author_cannot_review(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.post(
            self.review_url, {"action": "approve"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_editor_can_approve(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(
            self.review_url,
            {"action": "approve", "review_notes": "Looks good"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, Post.Status.APPROVED)
        self.assertEqual(self.post.reviewed_by, self.editor)
        self.assertIsNotNone(self.post.reviewed_at)
        self.assertEqual(self.post.review_notes, "Looks good")

    def test_reject_requires_notes(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(
            self.review_url, {"action": "reject"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, Post.Status.UNDER_REVIEW)

    def test_reject_with_notes_returns_post_to_draft(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(
            self.review_url,
            {"action": "reject", "review_notes": "Needs work"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, Post.Status.DRAFT)
        self.assertEqual(self.post.review_notes, "Needs work")

    def test_invalid_action_is_rejected(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(
            self.review_url, {"action": "explode"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_only_under_review_posts_can_be_reviewed(self):
        """Fails until the broken `{ {...}, }` response in PostReviewView is fixed."""
        draft = self.make_post(self.author, "Draft", status=Post.Status.DRAFT)
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(
            url("post-review", post_id=draft.id), {"action": "approve"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_review_unknown_post_is_404(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(
            url("post-review", post_id=uuid.uuid4()),
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ============================================================
# PUBLISH / SCHEDULE
# ============================================================
class PostPublishTests(BlogTestBase):
    def setUp(self):
        super().setUp()
        self.post = self.make_post(self.author, status=Post.Status.APPROVED)
        self.publish_url = url("post-publish", post_id=self.post.id)

    def test_anonymous_cannot_publish(self):
        response = self.client.post(
            self.publish_url, {"action": "publish"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_author_cannot_publish(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.post(
            self.publish_url, {"action": "publish"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_editor_can_publish_approved_post(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(
            self.publish_url, {"action": "publish"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.post.refresh_from_db()
        self.assertEqual(self.post.status, Post.Status.PUBLISHED)
        self.assertIsNotNone(self.post.published_at)

    def test_published_post_appears_in_public_list(self):
        self.client.force_authenticate(user=self.editor)
        self.client.post(self.publish_url, {"action": "publish"}, format="json")
        self.client.force_authenticate(user=None)

        response = self.client.get(url("post-list-create"))
        self.assertEqual(len(results(response)), 1)

    def test_cannot_publish_unapproved_post(self):
        draft = self.make_post(self.author, "Draft", status=Post.Status.DRAFT)
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(
            url("post-publish", post_id=draft.id),
            {"action": "publish"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        draft.refresh_from_db()
        self.assertEqual(draft.status, Post.Status.DRAFT)

    def test_schedule_requires_scheduled_at(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(
            self.publish_url, {"action": "schedule"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_schedule_rejects_past_time(self):
        self.client.force_authenticate(user=self.editor)
        past = (timezone.now() - timedelta(hours=1)).isoformat()
        response = self.client.post(
            self.publish_url,
            {"action": "schedule", "scheduled_at": past},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_schedule_with_future_time_succeeds(self):
        self.client.force_authenticate(user=self.editor)
        future = (timezone.now() + timedelta(days=1)).isoformat()
        response = self.client.post(
            self.publish_url,
            {"action": "schedule", "scheduled_at": future},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.post.refresh_from_db()
        self.assertIsNotNone(self.post.scheduled_at)
        self.assertEqual(self.post.status, Post.Status.APPROVED)

    def test_publish_rejects_scheduled_at(self):
        self.client.force_authenticate(user=self.editor)
        future = (timezone.now() + timedelta(days=1)).isoformat()
        response = self.client.post(
            self.publish_url,
            {"action": "publish", "scheduled_at": future},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_publish_unknown_post_is_404(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(
            url("post-publish", post_id=uuid.uuid4()),
            {"action": "publish"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ============================================================
# FULL WORKFLOW
# ============================================================
class PostWorkflowTests(BlogTestBase):
    def test_draft_to_published_end_to_end(self):
        # author creates a draft
        self.client.force_authenticate(user=self.author)
        response = self.client.post(
            url("post-list-create"),
            {"title": "Journey", "content": "Body"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        post_id = response.data["id"]

        # not visible to the public yet
        self.client.force_authenticate(user=None)
        response = self.client.get(url("post-detail", post_id=post_id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # author submits for review
        self.client.force_authenticate(user=self.author)
        response = self.client.post(
            url("post-submit-review", post_id=post_id),
            {"action": "submit"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # editor approves, then publishes
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(
            url("post-review", post_id=post_id), {"action": "approve"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.post(
            url("post-publish", post_id=post_id), {"action": "publish"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # now the public can read it
        self.client.force_authenticate(user=None)
        response = self.client.get(url("post-detail", post_id=post_id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)


# ============================================================
# CATEGORIES
# ============================================================
class CategoryTests(BlogTestBase):
    def setUp(self):
        super().setUp()
        self.category = Category.objects.create(name="News", slug="news")
        self.detail = url("category-detail", category_id=self.category.id)

    def test_anyone_can_list_categories(self):
        response = self.client.get(url("category-list-create"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(results(response)), 1)

    def test_anyone_can_read_category(self):
        response = self.client.get(self.detail)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unknown_category_is_404(self):
        response = self.client.get(url("category-detail", category_id=uuid.uuid4()))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_cannot_create(self):
        response = self.client.post(
            url("category-list-create"),
            {"name": "Tech", "slug": "tech"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_author_cannot_create(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.post(
            url("category-list-create"),
            {"name": "Tech", "slug": "tech"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_editor_can_create(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(
            url("category-list-create"),
            {"name": "Tech", "slug": "tech"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Category.objects.filter(slug="tech").exists())

    def test_duplicate_name_rejected(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(
            url("category-list-create"),
            {"name": "News", "slug": "news-2"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_slug_rejected(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(
            url("category-list-create"),
            {"name": "Other", "slug": "news"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_author_cannot_update_or_delete(self):
        self.client.force_authenticate(user=self.author)
        self.assertEqual(
            self.client.patch(self.detail, {"name": "X"}, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.delete(self.detail).status_code, status.HTTP_403_FORBIDDEN
        )

    def test_editor_can_update(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.patch(self.detail, {"name": "Headlines"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Headlines")

    def test_editor_can_delete(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.delete(self.detail)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Category.objects.filter(id=self.category.id).exists())


# ============================================================
# TAGS
# ============================================================
class TagTests(BlogTestBase):
    def setUp(self):
        super().setUp()
        self.tag = Tag.objects.create(name="Django", slug="django")
        self.detail = url("tag-detail", tag_id=self.tag.id)

    def test_anyone_can_list_tags(self):
        response = self.client.get(url("tag-list-create"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(results(response)), 1)

    def test_anyone_can_read_tag(self):
        response = self.client.get(self.detail)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unknown_tag_is_404(self):
        response = self.client.get(url("tag-detail", tag_id=uuid.uuid4()))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_author_cannot_create(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.post(
            url("tag-list-create"), {"name": "DRF", "slug": "drf"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_editor_can_create(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(
            url("tag-list-create"), {"name": "DRF", "slug": "drf"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_duplicate_tag_rejected(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(
            url("tag-list-create"),
            {"name": "Django", "slug": "django-2"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_author_cannot_update_or_delete(self):
        self.client.force_authenticate(user=self.author)
        self.assertEqual(
            self.client.patch(self.detail, {"name": "X"}, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.delete(self.detail).status_code, status.HTTP_403_FORBIDDEN
        )

    def test_editor_can_update_and_delete(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.patch(self.detail, {"name": "DjangoX"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.delete(self.detail)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


# ============================================================
# KNOWN PROBLEMS
# These are expected to FAIL until the bugs are fixed.
# ============================================================
class KnownIssueTests(BlogTestBase):
    def test_public_post_does_not_expose_review_data(self):
        post = self.make_post(
            self.author,
            status=Post.Status.PUBLISHED,
            review_notes="internal note",
        )
        response = self.client.get(url("post-detail", post_id=post.id))
        self.assertNotIn("review_notes", response.data)
        self.assertNotIn("reviewed_by", response.data)

    def test_invalid_author_filter_does_not_crash(self):
        self.client.raise_request_exception = False
        response = self.client.get(url("post-list-create"), {"author": "not-a-uuid"})
        self.assertLess(response.status_code, 500)

    def test_author_name_is_shown(self):
        post = self.make_post(self.author, status=Post.Status.PUBLISHED)
        response = self.client.get(url("post-detail", post_id=post.id))
        self.assertIn("author_name", response.data)

    def test_author_cannot_set_featured_or_trending(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.post(
            url("post-list-create"),
            {"title": "Sneaky", "content": "x", "is_featured": True, "is_trending": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        post = Post.objects.get(title="Sneaky")
        self.assertFalse(post.is_featured)
        self.assertFalse(post.is_trending)