from unittest.mock import patch

from django.urls import reverse, NoReverseMatch
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from blog.models import Post
from comments.models import Comment
from engagements.models import Follow

from .models import Notification
from .services import create_notification

COMMENT = Notification.NotificationType.COMMENT
REPLY = Notification.NotificationType.REPLY
REACTION = Notification.NotificationType.REACTION
BOOKMARK = Notification.NotificationType.BOOKMARK
FOLLOW = Notification.NotificationType.FOLLOW
PUBLISH = Notification.NotificationType.PUBLISH


def url(name, **kwargs):
    """Reverse a URL, with or without the /api/<version>/ kwarg."""
    try:
        return reverse(name, kwargs={"version": "v1", **kwargs})
    except NoReverseMatch:
        return reverse(name, kwargs=kwargs)


class TriggerTestBase(APITestCase):
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

    def setUp(self):
        self.admin = self.make_user(User.Role.ADMIN, "admin1")
        self.editor = self.make_user(User.Role.EDITOR, "editor1")
        self.author = self.make_user(User.Role.AUTHOR, "author1")
        self.reader = self.make_user(User.Role.SUBSCRIBER, "reader1")
        self.other_reader = self.make_user(User.Role.SUBSCRIBER, "reader2")

        self.post = Post.objects.create(
            author=self.author,
            title="A post",
            content="Body",
            status=Post.Status.PUBLISHED,
        )

    def notes(self, user, notification_type=None):
        queryset = Notification.objects.filter(recipient=user)
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        return queryset


# ============================================================
# THE SERVICE ITSELF
# ============================================================
class CreateNotificationTests(TriggerTestBase):
    def test_creates_a_notification(self):
        note = create_notification(
            recipient=self.reader,
            actor=self.author,
            notification_type=COMMENT,
            title="Hello",
            message="World",
            related_object_id=123,
            related_url="/somewhere",
        )
        self.assertEqual(note.recipient, self.reader)
        self.assertEqual(note.actor, self.author)
        self.assertEqual(note.title, "Hello")
        self.assertEqual(note.related_object_id, "123")
        self.assertFalse(note.is_read)

    def test_never_notifies_you_about_your_own_action(self):
        note = create_notification(
            recipient=self.reader,
            actor=self.reader,
            notification_type=COMMENT,
            title="t",
            message="m",
        )
        self.assertIsNone(note)
        self.assertEqual(Notification.objects.count(), 0)

    def test_unknown_type_creates_nothing(self):
        note = create_notification(
            recipient=self.reader,
            notification_type="bogus",
            title="t",
            message="m",
        )
        self.assertIsNone(note)
        self.assertEqual(Notification.objects.count(), 0)

    def test_missing_recipient_creates_nothing(self):
        note = create_notification(
            recipient=None, notification_type=COMMENT, title="t", message="m"
        )
        self.assertIsNone(note)

    def test_dedupe_blocks_the_second_identical_notification(self):
        kwargs = dict(
            recipient=self.author,
            actor=self.reader,
            notification_type=REACTION,
            title="t",
            message="m",
            related_object_id=self.post.id,
            dedupe=True,
        )
        self.assertIsNotNone(create_notification(**kwargs))
        self.assertIsNone(create_notification(**kwargs))
        self.assertEqual(Notification.objects.count(), 1)

    def test_dedupe_still_allows_other_actors(self):
        for actor in (self.reader, self.other_reader):
            create_notification(
                recipient=self.author,
                actor=actor,
                notification_type=REACTION,
                title="t",
                message="m",
                related_object_id=self.post.id,
                dedupe=True,
            )
        self.assertEqual(Notification.objects.count(), 2)

    def test_database_failure_does_not_raise(self):
        with patch.object(Notification.objects, "create", side_effect=Exception("db down")):
            note = create_notification(
                recipient=self.reader,
                notification_type=COMMENT,
                title="t",
                message="m",
            )
        self.assertIsNone(note)


# ============================================================
# COMMENTS
# ============================================================
class CommentNotificationTests(TriggerTestBase):
    def make_comment(self, author, state=Comment.Status.PENDING, parent=None):
        return Comment.objects.create(
            post=self.post, author=author, content="Nice", status=state, parent=parent
        )

    def moderate(self, comment, action="approve"):
        self.client.force_authenticate(user=self.editor)
        return self.client.post(
            url("comment-moderate", comment_id=comment.id),
            {"action": action},
            format="json",
        )

    def test_approved_comment_notifies_the_post_author(self):
        comment = self.make_comment(self.reader)
        self.moderate(comment)

        note = self.notes(self.author, COMMENT).get()
        self.assertEqual(note.actor, self.reader)
        self.assertEqual(note.related_object_id, str(comment.id))
        self.assertIn(self.post.slug, note.related_url)
        self.assertTrue(note.title)
        self.assertIn("A post", note.message)

    def test_pending_comment_notifies_nobody(self):
        self.make_comment(self.reader)
        self.assertEqual(Notification.objects.count(), 0)

    def test_creating_a_comment_through_the_api_notifies_nobody_yet(self):
        self.client.force_authenticate(user=self.reader)
        self.client.post(
            url("comment-list-create"),
            {"post": str(self.post.id), "content": "Hello"},
            format="json",
        )
        self.assertEqual(Notification.objects.count(), 0)

    def test_rejected_comment_notifies_nobody(self):
        comment = self.make_comment(self.reader)
        self.moderate(comment, action="reject")
        self.assertEqual(Notification.objects.count(), 0)

    def test_authors_own_comment_does_not_notify_them(self):
        comment = self.make_comment(self.author)
        self.moderate(comment)
        self.assertEqual(self.notes(self.author).count(), 0)

    def test_approved_reply_notifies_the_parent_comment_author(self):
        parent = self.make_comment(self.other_reader, state=Comment.Status.APPROVED)
        reply = self.make_comment(self.reader, parent=parent)
        self.moderate(reply)

        note = self.notes(self.other_reader, REPLY).get()
        self.assertEqual(note.actor, self.reader)
        self.assertEqual(note.related_object_id, str(reply.id))
        # the post author is not told about a reply to someone else's comment
        self.assertEqual(self.notes(self.author).count(), 0)

    def test_replying_to_your_own_comment_notifies_nobody(self):
        parent = self.make_comment(self.reader, state=Comment.Status.APPROVED)
        reply = self.make_comment(self.reader, parent=parent)
        self.moderate(reply)
        self.assertEqual(Notification.objects.count(), 0)


# ============================================================
# REACTIONS, BOOKMARKS, FOLLOWS
# ============================================================
class EngagementNotificationTests(TriggerTestBase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.reader)
        self.reaction_url = url("post-reaction", post_id=self.post.id)
        self.bookmark_url = url("post-bookmark", post_id=self.post.id)
        self.follow_url = url("user-follow", user_id=self.author.id)

    def react(self, value="like"):
        return self.client.post(
            self.reaction_url, {"reaction_type": value}, format="json"
        )

    # ----- reactions -----
    def test_reaction_notifies_the_post_author(self):
        self.react()
        note = self.notes(self.author, REACTION).get()
        self.assertEqual(note.actor, self.reader)
        self.assertEqual(note.related_object_id, str(self.post.id))
        self.assertIn(self.post.slug, note.related_url)

    def test_changing_a_reaction_does_not_notify_again(self):
        self.react("like")
        self.react("love")
        self.assertEqual(self.notes(self.author, REACTION).count(), 1)

    def test_toggling_a_reaction_notifies_once(self):
        for _ in range(3):
            self.react()
            self.client.delete(self.reaction_url)
        self.react()
        self.assertEqual(self.notes(self.author, REACTION).count(), 1)

    def test_reacting_to_your_own_post_notifies_nobody(self):
        self.client.force_authenticate(user=self.author)
        self.react()
        self.assertEqual(Notification.objects.count(), 0)

    def test_two_readers_reacting_notify_twice(self):
        self.react()
        self.client.force_authenticate(user=self.other_reader)
        self.react()
        self.assertEqual(self.notes(self.author, REACTION).count(), 2)

    # ----- bookmarks -----
    def test_bookmark_notifies_the_post_author(self):
        self.client.post(self.bookmark_url)
        note = self.notes(self.author, BOOKMARK).get()
        self.assertEqual(note.actor, self.reader)

    def test_toggling_a_bookmark_notifies_once(self):
        for _ in range(3):
            self.client.post(self.bookmark_url)
            self.client.delete(self.bookmark_url)
        self.client.post(self.bookmark_url)
        self.assertEqual(self.notes(self.author, BOOKMARK).count(), 1)

    def test_bookmarking_your_own_post_notifies_nobody(self):
        self.client.force_authenticate(user=self.author)
        self.client.post(self.bookmark_url)
        self.assertEqual(Notification.objects.count(), 0)

    # ----- follows -----
    def test_follow_notifies_the_followed_user(self):
        self.client.post(self.follow_url)
        note = self.notes(self.author, FOLLOW).get()
        self.assertEqual(note.actor, self.reader)
        self.assertEqual(note.related_object_id, str(self.reader.id))

    def test_toggling_a_follow_notifies_once(self):
        for _ in range(3):
            self.client.post(self.follow_url)
            self.client.delete(self.follow_url)
        self.client.post(self.follow_url)
        self.assertEqual(self.notes(self.author, FOLLOW).count(), 1)

    def test_following_twice_notifies_once(self):
        self.client.post(self.follow_url)
        self.client.post(self.follow_url)
        self.assertEqual(self.notes(self.author, FOLLOW).count(), 1)


# ============================================================
# PUBLISHING
# ============================================================
class PublishNotificationTests(TriggerTestBase):
    def setUp(self):
        super().setUp()
        self.draft = Post.objects.create(
            author=self.author,
            title="Fresh post",
            content="Body",
            status=Post.Status.APPROVED,
        )
        self.publish_url = url("post-publish", post_id=self.draft.id)

    def publish(self):
        self.client.force_authenticate(user=self.editor)
        return self.client.post(self.publish_url, {"action": "publish"}, format="json")

    def test_followers_are_notified(self):
        Follow.objects.create(follower=self.reader, following=self.author)
        Follow.objects.create(follower=self.other_reader, following=self.author)

        response = self.publish()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for follower in (self.reader, self.other_reader):
            note = self.notes(follower, PUBLISH).get()
            self.assertEqual(note.actor, self.author)
            self.assertEqual(note.related_object_id, str(self.draft.id))
            self.assertIn(self.draft.slug, note.related_url)

    def test_people_who_do_not_follow_are_not_notified(self):
        Follow.objects.create(follower=self.reader, following=self.author)
        self.publish()
        self.assertEqual(self.notes(self.other_reader).count(), 0)

    def test_following_a_different_author_does_not_count(self):
        Follow.objects.create(follower=self.reader, following=self.editor)
        self.publish()
        self.assertEqual(self.notes(self.reader).count(), 0)

    def test_author_is_told_when_an_editor_publishes_their_post(self):
        self.publish()
        note = self.notes(self.author, PUBLISH).get()
        self.assertEqual(note.actor, self.editor)

    def test_scheduling_does_not_notify_anyone_yet(self):
        from datetime import timedelta
        from django.utils import timezone

        Follow.objects.create(follower=self.reader, following=self.author)
        self.client.force_authenticate(user=self.editor)
        self.client.post(
            self.publish_url,
            {
                "action": "schedule",
                "scheduled_at": (timezone.now() + timedelta(days=1)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(Notification.objects.count(), 0)

    def test_publishing_with_no_followers_still_works(self):
        response = self.publish()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, Post.Status.PUBLISHED)


# ============================================================
# A NOTIFICATION FAILURE MUST NEVER BREAK THE ACTION
# ============================================================
class ResilienceTests(TriggerTestBase):
    def broken(self):
        return patch.object(Notification.objects, "create", side_effect=Exception("db down"))

    def test_reaction_survives(self):
        self.client.force_authenticate(user=self.reader)
        with self.broken():
            response = self.client.post(
                url("post-reaction", post_id=self.post.id),
                {"reaction_type": "like"},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_bookmark_survives(self):
        self.client.force_authenticate(user=self.reader)
        with self.broken():
            response = self.client.post(url("post-bookmark", post_id=self.post.id))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_follow_survives(self):
        self.client.force_authenticate(user=self.reader)
        with self.broken():
            response = self.client.post(url("user-follow", user_id=self.author.id))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_comment_approval_survives(self):
        comment = Comment.objects.create(
            post=self.post, author=self.reader, content="Hi", status=Comment.Status.PENDING
        )
        self.client.force_authenticate(user=self.editor)
        with self.broken():
            response = self.client.post(
                url("comment-moderate", comment_id=comment.id),
                {"action": "approve"},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        comment.refresh_from_db()
        self.assertEqual(comment.status, Comment.Status.APPROVED)

    def test_publishing_survives(self):
        draft = Post.objects.create(
            author=self.author, title="Fresh", content="Body", status=Post.Status.APPROVED
        )
        self.client.force_authenticate(user=self.editor)
        with self.broken():
            response = self.client.post(
                url("post-publish", post_id=draft.id), {"action": "publish"}, format="json"
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)