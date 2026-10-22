import uuid
from unittest.mock import patch

from django.urls import reverse, NoReverseMatch
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from analytics.models import AnalyticsEvent
from blog.models import Post

from .models import Comment
from .views import CommentListCreateView

PENDING = Comment.Status.PENDING
APPROVED = Comment.Status.APPROVED
REJECTED = Comment.Status.REJECTED
DELETED = Comment.Status.DELETED


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


class CommentTestBase(APITestCase):
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

    def make_post(self, title="A post", **kwargs):
        kwargs.setdefault("status", Post.Status.PUBLISHED)
        return Post.objects.create(
            author=self.author, title=title, content="Body", **kwargs
        )

    def make_comment(
        self, post=None, author=None, content="A comment", state=APPROVED, parent=None
    ):
        return Comment.objects.create(
            post=post or self.post,
            author=author or self.subscriber,
            content=content,
            status=state,
            parent=parent,
        )

    def setUp(self):
        self.admin = self.make_user(User.Role.ADMIN, "admin1")
        self.editor = self.make_user(User.Role.EDITOR, "editor1")
        self.author = self.make_user(User.Role.AUTHOR, "author1")  # owns self.post
        self.other_author = self.make_user(User.Role.AUTHOR, "author2")
        self.contributor = self.make_user(User.Role.CONTRIBUTOR, "contrib1")
        self.subscriber = self.make_user(User.Role.SUBSCRIBER, "reader1")
        self.other_reader = self.make_user(User.Role.SUBSCRIBER, "reader2")

        self.post = self.make_post()
        self.list_url = url("comment-list-create")

    def payload(self, **overrides):
        data = {"post": str(self.post.id), "content": "Nice post"}
        data.update(overrides)
        return data


# ============================================================
# MODEL
# ============================================================
class CommentModelTests(CommentTestBase):
    def test_new_comment_defaults_to_pending(self):
        comment = Comment.objects.create(
            post=self.post, author=self.subscriber, content="Hello"
        )
        self.assertEqual(comment.status, PENDING)
        self.assertEqual(comment.likes, 0)
        self.assertIsNone(comment.edited_at)

    def test_replies_relation(self):
        parent = self.make_comment()
        reply = self.make_comment(parent=parent, author=self.other_reader)
        self.assertEqual(list(parent.replies.all()), [reply])

    def test_deleting_post_deletes_its_comments(self):
        self.make_comment()
        self.post.delete()
        self.assertEqual(Comment.objects.count(), 0)

    def test_deleting_parent_deletes_replies(self):
        parent = self.make_comment()
        self.make_comment(parent=parent, author=self.other_reader)
        parent.delete()
        self.assertEqual(Comment.objects.count(), 0)


# ============================================================
# PUBLIC LIST
# ============================================================
class CommentListTests(CommentTestBase):
    def test_anonymous_sees_only_approved_comments(self):
        self.make_comment(content="Visible", state=APPROVED)
        self.make_comment(content="Pending", state=PENDING)
        self.make_comment(content="Rejected", state=REJECTED)
        self.make_comment(content="Deleted", state=DELETED)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([c["content"] for c in results(response)], ["Visible"])

    def test_filter_by_post(self):
        other_post = self.make_post("Other post")
        self.make_comment(content="On first")
        self.make_comment(post=other_post, content="On other")

        response = self.client.get(self.list_url, {"post": str(self.post.id)})

        self.assertEqual([c["content"] for c in results(response)], ["On first"])

    def test_comments_are_oldest_first(self):
        self.make_comment(content="first")
        self.make_comment(content="second")
        response = self.client.get(self.list_url)
        self.assertEqual([c["content"] for c in results(response)], ["first", "second"])

    def test_comment_shows_author_name(self):
        self.make_comment(author=self.subscriber)
        item = results(self.client.get(self.list_url))[0]
        self.assertEqual(item["author_name"], "Reader1 Tester")

    def test_reply_appears_with_parent_id(self):
        parent = self.make_comment(content="parent")
        self.make_comment(content="reply", parent=parent, author=self.other_reader)

        items = {c["content"]: c for c in results(self.client.get(self.list_url))}

        self.assertEqual(str(items["reply"]["parent"]), str(parent.id))
        self.assertIsNone(items["parent"]["parent"])

    def test_replies_count_counts_approved_replies(self):
        parent = self.make_comment(content="parent")
        self.make_comment(content="reply", parent=parent, author=self.other_reader)

        items = {c["content"]: c for c in results(self.client.get(self.list_url))}

        self.assertEqual(items["parent"]["replies_count"], 1)


# ============================================================
# CREATE
# ============================================================
class CommentCreateTests(CommentTestBase):
    def test_anonymous_cannot_comment(self):
        response = self.client.post(self.list_url, self.payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_subscriber_can_comment_and_it_starts_pending(self):
        self.client.force_authenticate(user=self.subscriber)
        response = self.client.post(self.list_url, self.payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        comment = Comment.objects.get()
        self.assertEqual(comment.author, self.subscriber)
        self.assertEqual(comment.post, self.post)
        self.assertEqual(comment.status, PENDING)
        self.assertEqual(response.data["status"], "pending")

    def test_new_comment_is_not_public_until_approved(self):
        self.client.force_authenticate(user=self.subscriber)
        self.client.post(self.list_url, self.payload(), format="json")
        self.client.force_authenticate(user=None)
        self.assertEqual(results(self.client.get(self.list_url)), [])

    def test_content_is_required(self):
        self.client.force_authenticate(user=self.subscriber)
        data = self.payload()
        data.pop("content")
        response = self.client.post(self.list_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_and_blank_content_rejected(self):
        self.client.force_authenticate(user=self.subscriber)
        for value in ("", "   "):
            with self.subTest(content=value):
                response = self.client.post(
                    self.list_url, self.payload(content=value), format="json"
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_is_required(self):
        self.client.force_authenticate(user=self.subscriber)
        response = self.client.post(
            self.list_url, {"content": "No post given"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_post_is_rejected(self):
        self.client.force_authenticate(user=self.subscriber)
        response = self.client.post(
            self.list_url, self.payload(post=str(uuid.uuid4())), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_comment_on_draft_post(self):
        draft = self.make_post("Draft", status=Post.Status.DRAFT)
        self.client.force_authenticate(user=self.subscriber)
        response = self.client.post(
            self.list_url, self.payload(post=str(draft.id)), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_comment_on_private_post(self):
        private = self.make_post("Private", visibility=Post.Visibility.PRIVATE)
        self.client.force_authenticate(user=self.subscriber)
        response = self.client.post(
            self.list_url, self.payload(post=str(private.id)), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_comment_when_comments_disabled(self):
        closed = self.make_post("Closed", allow_comments=False)
        self.client.force_authenticate(user=self.subscriber)
        response = self.client.post(
            self.list_url, self.payload(post=str(closed.id)), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_cannot_set_own_status(self):
        self.client.force_authenticate(user=self.subscriber)
        self.client.post(
            self.list_url, self.payload(status="approved"), format="json"
        )
        self.assertEqual(Comment.objects.get().status, PENDING)

    def test_user_cannot_choose_author_or_likes(self):
        self.client.force_authenticate(user=self.subscriber)
        self.client.post(
            self.list_url,
            self.payload(author=self.admin.id, likes=999),
            format="json",
        )
        comment = Comment.objects.get()
        self.assertEqual(comment.author, self.subscriber)
        self.assertEqual(comment.likes, 0)

    def test_can_reply_to_approved_comment(self):
        parent = self.make_comment()
        self.client.force_authenticate(user=self.other_reader)
        response = self.client.post(
            self.list_url, self.payload(parent=str(parent.id)), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Comment.objects.get(author=self.other_reader).parent, parent)

    def test_cannot_reply_to_pending_comment(self):
        parent = self.make_comment(state=PENDING)
        self.client.force_authenticate(user=self.other_reader)
        response = self.client.post(
            self.list_url, self.payload(parent=str(parent.id)), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_reply_across_posts(self):
        other_post = self.make_post("Other post")
        parent = self.make_comment(post=other_post)
        self.client.force_authenticate(user=self.other_reader)
        response = self.client.post(
            self.list_url, self.payload(parent=str(parent.id)), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ============================================================
# EDIT
# ============================================================
class CommentEditTests(CommentTestBase):
    def setUp(self):
        super().setUp()
        self.comment = self.make_comment(author=self.subscriber, content="Original")
        self.detail = url("comment-detail", comment_id=self.comment.id)

    def test_anonymous_cannot_edit(self):
        response = self.client.patch(self.detail, {"content": "X"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_owner_can_edit_content(self):
        self.client.force_authenticate(user=self.subscriber)
        response = self.client.patch(
            self.detail, {"content": "Edited"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.content, "Edited")
        self.assertIsNotNone(self.comment.edited_at)

    def test_non_owner_cannot_edit(self):
        for user in (self.other_reader, self.editor, self.admin):
            with self.subTest(role=user.role):
                self.client.force_authenticate(user=user)
                response = self.client.patch(
                    self.detail, {"content": "Hacked"}, format="json"
                )
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.content, "Original")

    def test_edit_unknown_comment_is_404(self):
        self.client.force_authenticate(user=self.subscriber)
        response = self.client.patch(
            url("comment-detail", comment_id=uuid.uuid4()),
            {"content": "X"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_edit_cannot_change_status(self):
        pending = self.make_comment(state=PENDING, author=self.subscriber)
        self.client.force_authenticate(user=self.subscriber)
        self.client.patch(
            url("comment-detail", comment_id=pending.id),
            {"status": "approved"},
            format="json",
        )
        pending.refresh_from_db()
        self.assertEqual(pending.status, PENDING)

    def test_edit_cannot_change_author(self):
        self.client.force_authenticate(user=self.subscriber)
        self.client.patch(
            self.detail,
            {"content": "Edited", "author": self.admin.id},
            format="json",
        )
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.author, self.subscriber)

    def test_edit_rejects_blank_content(self):
        self.client.force_authenticate(user=self.subscriber)
        response = self.client.patch(self.detail, {"content": "  "}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ============================================================
# DELETE (soft delete)
# ============================================================
class CommentDeleteTests(CommentTestBase):
    def setUp(self):
        super().setUp()
        self.comment = self.make_comment(author=self.subscriber)
        self.detail = url("comment-detail", comment_id=self.comment.id)

    def test_anonymous_cannot_delete(self):
        response = self.client.delete(self.detail)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_owner_can_delete_and_it_is_soft(self):
        self.client.force_authenticate(user=self.subscriber)
        response = self.client.delete(self.detail)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.comment.refresh_from_db()  # still in the database
        self.assertEqual(self.comment.status, DELETED)

    def test_deleted_comment_disappears_from_list(self):
        self.client.force_authenticate(user=self.subscriber)
        self.client.delete(self.detail)
        self.client.force_authenticate(user=None)
        self.assertEqual(results(self.client.get(self.list_url)), [])

    def test_other_users_cannot_delete(self):
        for user in (self.other_reader, self.contributor):
            with self.subTest(role=user.role):
                self.client.force_authenticate(user=user)
                response = self.client.delete(self.detail)
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.status, APPROVED)

    def test_editor_can_delete_any_comment(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.delete(self.detail)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_can_delete_any_comment(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.delete(self.detail)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_unknown_comment_is_404(self):
        self.client.force_authenticate(user=self.subscriber)
        response = self.client.delete(url("comment-detail", comment_id=uuid.uuid4()))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ============================================================
# MODERATION
# ============================================================
class CommentModerationTests(CommentTestBase):
    def setUp(self):
        super().setUp()
        self.comment = self.make_comment(state=PENDING, author=self.subscriber)
        self.moderate = url("comment-moderate", comment_id=self.comment.id)

    def act(self, action):
        return self.client.post(self.moderate, {"action": action}, format="json")

    def test_anonymous_cannot_moderate(self):
        self.assertEqual(self.act("approve").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_subscriber_and_contributor_cannot_moderate(self):
        for user in (self.subscriber, self.contributor):
            with self.subTest(role=user.role):
                self.client.force_authenticate(user=user)
                self.assertEqual(
                    self.act("approve").status_code, status.HTTP_403_FORBIDDEN
                )
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.status, PENDING)

    def test_editor_can_approve(self):
        self.client.force_authenticate(user=self.editor)
        response = self.act("approve")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["comment"]["status"], "approved")
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.status, APPROVED)

    def test_admin_can_reject(self):
        self.client.force_authenticate(user=self.admin)
        response = self.act("reject")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.status, REJECTED)

    def test_post_owner_can_moderate_comments_on_own_post(self):
        self.client.force_authenticate(user=self.author)
        self.assertEqual(self.act("approve").status_code, status.HTTP_200_OK)

    def test_approved_comment_becomes_public(self):
        self.client.force_authenticate(user=self.editor)
        self.act("approve")
        self.client.force_authenticate(user=None)
        self.assertEqual(len(results(self.client.get(self.list_url))), 1)

    def test_rejected_comment_stays_hidden(self):
        self.client.force_authenticate(user=self.editor)
        self.act("reject")
        self.client.force_authenticate(user=None)
        self.assertEqual(results(self.client.get(self.list_url)), [])

    def test_invalid_or_missing_action_is_400(self):
        self.client.force_authenticate(user=self.editor)
        self.assertEqual(self.act("explode").status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.post(self.moderate, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_only_pending_comments_can_be_moderated(self):
        approved = self.make_comment(state=APPROVED)
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(
            url("comment-moderate", comment_id=approved.id),
            {"action": "reject"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        approved.refresh_from_db()
        self.assertEqual(approved.status, APPROVED)

    def test_moderate_unknown_comment_is_404(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.post(
            url("comment-moderate", comment_id=uuid.uuid4()),
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_approval_survives_analytics_failure(self):
        """Passes today. Guards the fix that records the event on approval."""
        self.client.force_authenticate(user=self.editor)
        self.client.raise_request_exception = False
        target = f"{CommentListCreateView.__module__}.record_event"
        with patch(target, side_effect=Exception("analytics down")):
            response = self.act("approve")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.status, APPROVED)


# ============================================================
# KNOWN PROBLEMS
# These are expected to FAIL until the bugs are fixed.
# ============================================================
class KnownIssueTests(CommentTestBase):
    def test_other_author_cannot_moderate_comment_on_someone_elses_post(self):
        comment = self.make_comment(state=PENDING)  # on self.post, owned by author1
        self.client.force_authenticate(user=self.other_author)
        response = self.client.post(
            url("comment-moderate", comment_id=comment.id),
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        comment.refresh_from_db()
        self.assertEqual(comment.status, PENDING)

    def test_comments_on_private_post_are_not_listed(self):
        self.make_comment()
        self.post.visibility = Post.Visibility.PRIVATE
        self.post.save()
        self.assertEqual(results(self.client.get(self.list_url)), [])

    def test_comments_on_draft_post_are_not_listed(self):
        self.make_comment()
        self.post.status = Post.Status.DRAFT
        self.post.save()
        self.assertEqual(results(self.client.get(self.list_url)), [])

    def test_invalid_post_filter_does_not_crash(self):
        self.client.raise_request_exception = False
        response = self.client.get(self.list_url, {"post": "not-a-uuid"})
        self.assertLess(response.status_code, 500)

    def test_edit_cannot_move_comment_to_another_post(self):
        other_post = self.make_post("Other post")
        comment = self.make_comment(author=self.subscriber)
        self.client.force_authenticate(user=self.subscriber)
        self.client.patch(
            url("comment-detail", comment_id=comment.id),
            {"content": "Moved", "post": str(other_post.id)},
            format="json",
        )
        comment.refresh_from_db()
        self.assertEqual(comment.post, self.post)

    def test_deleted_comment_cannot_be_edited(self):
        comment = self.make_comment(author=self.subscriber, state=DELETED)
        self.client.force_authenticate(user=self.subscriber)
        response = self.client.patch(
            url("comment-detail", comment_id=comment.id),
            {"content": "Back from the dead"},
            format="json",
        )
        self.assertIn(response.status_code, (400, 403, 404))
        comment.refresh_from_db()
        self.assertNotEqual(comment.content, "Back from the dead")

    def test_pending_comment_does_not_count_as_engagement(self):
        self.client.force_authenticate(user=self.subscriber)
        self.client.post(self.list_url, self.payload(), format="json")
        self.assertEqual(
            AnalyticsEvent.objects.filter(
                event_type=AnalyticsEvent.EventType.COMMENT
            ).count(),
            0,
        )

    def test_approving_a_comment_records_comment_event(self):
        comment = self.make_comment(state=PENDING)
        self.client.force_authenticate(user=self.editor)
        self.client.post(
            url("comment-moderate", comment_id=comment.id),
            {"action": "approve"},
            format="json",
        )
        self.assertEqual(
            AnalyticsEvent.objects.filter(
                event_type=AnalyticsEvent.EventType.COMMENT, post=self.post
            ).count(),
            1,
        )

    def test_replies_count_ignores_unapproved_replies(self):
        parent = self.make_comment(content="parent")
        self.make_comment(content="hidden", parent=parent, state=PENDING)
        items = {c["content"]: c for c in results(self.client.get(self.list_url))}
        self.assertEqual(items["parent"]["replies_count"], 0)