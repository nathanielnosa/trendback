import uuid
from datetime import timedelta

from django.urls import reverse, NoReverseMatch
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from .models import Notification


# ============================================================
# HELPERS
# ============================================================
def url(name, **kwargs):
    """Reverse a URL, with or without the /api/<version>/ kwarg."""
    try:
        return reverse(name, kwargs={"version": "v1", **kwargs})
    except NoReverseMatch:
        return reverse(name, kwargs=kwargs)


class NotificationTestBase(APITestCase):
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

    def make_notification(self, recipient=None, **kwargs):
        kwargs.setdefault("notification_type", Notification.NotificationType.COMMENT)
        kwargs.setdefault("title", "New comment")
        kwargs.setdefault("message", "Someone commented on your post.")
        return Notification.objects.create(
            recipient=recipient or self.reader, **kwargs
        )

    def setUp(self):
        self.reader = self.make_user(User.Role.SUBSCRIBER, "reader1")
        self.other_reader = self.make_user(User.Role.SUBSCRIBER, "reader2")
        self.author = self.make_user(User.Role.AUTHOR, "author1")

        self.list_url = url("notification-list")
        self.unread_url = url("notification-unread")
        self.read_all_url = url("notification-mark-all-read")

        self.client.force_authenticate(user=self.reader)

    def detail_url(self, notification):
        return url("notification-detail", notification_id=notification.id)

    def read_url(self, notification):
        return url("notification-mark-read", notification_id=notification.id)


# ============================================================
# MODEL
# ============================================================
class NotificationModelTests(NotificationTestBase):
    def test_defaults(self):
        notification = self.make_notification()
        self.assertFalse(notification.is_read)
        self.assertIsNone(notification.read_at)

    def test_newest_first_by_default(self):
        old = self.make_notification(title="old")
        new = self.make_notification(title="new")
        Notification.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )
        self.assertEqual(list(Notification.objects.all()), [new, old])

    def test_deleting_recipient_deletes_notifications(self):
        self.make_notification(recipient=self.other_reader)
        self.other_reader.delete()
        self.assertEqual(Notification.objects.count(), 0)

    def test_deleting_actor_keeps_notification(self):
        notification = self.make_notification(actor=self.other_reader)
        self.other_reader.delete()
        notification.refresh_from_db()
        self.assertIsNone(notification.actor)


# ============================================================
# AUTHENTICATION
# ============================================================
class AuthRequiredTests(NotificationTestBase):
    def test_anonymous_gets_401_everywhere(self):
        self.client.force_authenticate(user=None)
        some_id = uuid.uuid4()
        targets = [
            ("get", self.list_url),
            ("get", self.unread_url),
            ("get", url("notification-detail", notification_id=some_id)),
            ("patch", url("notification-mark-read", notification_id=some_id)),
            ("patch", self.read_all_url),
        ]
        for method, target in targets:
            with self.subTest(method=method, target=target):
                response = getattr(self.client, method)(target)
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ============================================================
# LIST
# ============================================================
class NotificationListTests(NotificationTestBase):
    def test_empty_list(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["unread_count"], 0)
        self.assertEqual(response.data["notifications"], [])

    def test_shows_only_my_notifications(self):
        self.make_notification(title="mine")
        self.make_notification(recipient=self.other_reader, title="theirs")

        data = self.client.get(self.list_url).data

        self.assertEqual(data["count"], 1)
        self.assertEqual([n["title"] for n in data["notifications"]], ["mine"])

    def test_newest_first(self):
        old = self.make_notification(title="old")
        new = self.make_notification(title="new")
        Notification.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=1)
        )
        titles = [n["title"] for n in self.client.get(self.list_url).data["notifications"]]
        self.assertEqual(titles, ["new", "old"])

    def test_item_fields(self):
        self.make_notification(actor=self.author, related_url="/posts/abc")
        item = self.client.get(self.list_url).data["notifications"][0]
        for key in (
            "id", "recipient", "recipient_name", "actor", "actor_name",
            "notification_type", "title", "message", "related_object_id",
            "related_url", "is_read", "read_at", "created_at",
        ):
            self.assertIn(key, item)
        self.assertEqual(item["actor_name"], "author1")
        self.assertEqual(item["recipient_name"], "reader1")

    def test_system_notification_has_no_actor(self):
        self.make_notification()
        item = self.client.get(self.list_url).data["notifications"][0]
        self.assertIsNone(item["actor"])
        self.assertIsNone(item["actor_name"])

    def test_unread_count_ignores_filters_and_other_users(self):
        self.make_notification()
        self.make_notification()
        self.make_notification(is_read=True)
        self.make_notification(recipient=self.other_reader)

        data = self.client.get(self.list_url, {"is_read": "true"}).data

        self.assertEqual(data["count"], 1)  # filtered
        self.assertEqual(data["unread_count"], 2)  # always all my unread

    def test_filter_is_read_true_and_false(self):
        self.make_notification(title="unread")
        self.make_notification(title="read", is_read=True)

        read = self.client.get(self.list_url, {"is_read": "true"}).data
        unread = self.client.get(self.list_url, {"is_read": "false"}).data

        self.assertEqual([n["title"] for n in read["notifications"]], ["read"])
        self.assertEqual([n["title"] for n in unread["notifications"]], ["unread"])

    def test_filter_by_type(self):
        self.make_notification(title="c", notification_type="comment")
        self.make_notification(title="f", notification_type="follow")

        data = self.client.get(self.list_url, {"type": "follow"}).data

        self.assertEqual([n["title"] for n in data["notifications"]], ["f"])

    def test_unknown_type_returns_empty_list(self):
        self.make_notification()
        data = self.client.get(self.list_url, {"type": "bogus"}).data
        self.assertEqual(data["notifications"], [])

    def test_first_page_has_ten_items(self):
        for i in range(12):
            self.make_notification(title=f"n{i}")
        data = self.client.get(self.list_url).data
        self.assertEqual(data["count"], 12)
        self.assertEqual(len(data["notifications"]), 10)

    def test_second_page(self):
        for i in range(12):
            self.make_notification(title=f"n{i}")
        data = self.client.get(self.list_url, {"page": 2}).data
        self.assertEqual(len(data["notifications"]), 2)

    def test_page_size_parameter(self):
        for i in range(8):
            self.make_notification(title=f"n{i}")
        data = self.client.get(self.list_url, {"page_size": 5}).data
        self.assertEqual(len(data["notifications"]), 5)

    def test_page_out_of_range_is_404(self):
        self.make_notification()
        response = self.client.get(self.list_url, {"page": 99})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ============================================================
# DETAIL
# ============================================================
class NotificationDetailTests(NotificationTestBase):
    def test_can_read_own_notification(self):
        notification = self.make_notification(title="Hello")
        response = self.client.get(self.detail_url(notification))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Hello")

    def test_viewing_does_not_mark_as_read(self):
        notification = self.make_notification()
        self.client.get(self.detail_url(notification))
        notification.refresh_from_db()
        self.assertFalse(notification.is_read)

    def test_cannot_read_someone_elses_notification(self):
        notification = self.make_notification(recipient=self.other_reader)
        response = self.client.get(self.detail_url(notification))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_notification_is_404(self):
        response = self.client.get(
            url("notification-detail", notification_id=uuid.uuid4())
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ============================================================
# MARK ONE AS READ
# ============================================================
class MarkReadTests(NotificationTestBase):
    def test_marks_notification_as_read(self):
        notification = self.make_notification()
        response = self.client.patch(self.read_url(notification))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["notification"]["is_read"])
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)

    def test_marking_twice_keeps_the_first_read_time(self):
        notification = self.make_notification()
        self.client.patch(self.read_url(notification))
        notification.refresh_from_db()
        first_read_at = notification.read_at

        response = self.client.patch(self.read_url(notification))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notification.refresh_from_db()
        self.assertEqual(notification.read_at, first_read_at)

    def test_cannot_mark_someone_elses_notification(self):
        notification = self.make_notification(recipient=self.other_reader)
        response = self.client.patch(self.read_url(notification))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        notification.refresh_from_db()
        self.assertFalse(notification.is_read)

    def test_unknown_notification_is_404(self):
        response = self.client.patch(
            url("notification-mark-read", notification_id=uuid.uuid4())
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_other_notifications_are_untouched(self):
        target = self.make_notification(title="target")
        other = self.make_notification(title="other")
        self.client.patch(self.read_url(target))
        other.refresh_from_db()
        self.assertFalse(other.is_read)

    def test_only_patch_is_allowed(self):
        notification = self.make_notification()
        response = self.client.post(self.read_url(notification))
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


# ============================================================
# MARK ALL AS READ
# ============================================================
class MarkAllReadTests(NotificationTestBase):
    def test_marks_all_my_unread_notifications(self):
        self.make_notification()
        self.make_notification()

        response = self.client.patch(self.read_all_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["updated_count"], 2)
        self.assertEqual(
            Notification.objects.filter(recipient=self.reader, is_read=False).count(), 0
        )

    def test_does_not_touch_other_users(self):
        theirs = self.make_notification(recipient=self.other_reader)
        self.make_notification()

        self.client.patch(self.read_all_url)

        theirs.refresh_from_db()
        self.assertFalse(theirs.is_read)

    def test_keeps_read_time_of_already_read_notifications(self):
        earlier = timezone.now() - timedelta(days=3)
        already = self.make_notification(is_read=True, read_at=earlier)
        self.make_notification()

        self.client.patch(self.read_all_url)

        already.refresh_from_db()
        self.assertEqual(already.read_at, earlier)

    def test_nothing_to_update(self):
        response = self.client.patch(self.read_all_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["updated_count"], 0)

    def test_unread_count_is_zero_afterwards(self):
        self.make_notification()
        self.client.patch(self.read_all_url)
        self.assertEqual(self.client.get(self.list_url).data["unread_count"], 0)


# ============================================================
# UNREAD LIST
# ============================================================
class UnreadListTests(NotificationTestBase):
    def test_shows_only_my_unread(self):
        self.make_notification(title="unread")
        self.make_notification(title="read", is_read=True)
        self.make_notification(recipient=self.other_reader, title="theirs")

        data = self.client.get(self.unread_url).data

        self.assertEqual(data["count"], 1)
        self.assertEqual([n["title"] for n in data["notifications"]], ["unread"])

    def test_empty(self):
        data = self.client.get(self.unread_url).data
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["notifications"], [])

    def test_item_becomes_read_after_marking(self):
        notification = self.make_notification()
        self.client.patch(self.read_url(notification))
        self.assertEqual(self.client.get(self.unread_url).data["count"], 0)


# ============================================================
# KNOWN PROBLEMS
# These are expected to FAIL until the bugs are fixed.
# ============================================================
class KnownIssueTests(NotificationTestBase):
    def test_list_includes_next_and_previous_links(self):
        for i in range(12):
            self.make_notification(title=f"n{i}")

        first_page = self.client.get(self.list_url).data

        self.assertIn("next", first_page)
        self.assertIn("previous", first_page)
        self.assertIsNotNone(first_page["next"])
        self.assertIsNone(first_page["previous"])

    def test_second_page_links_back(self):
        for i in range(12):
            self.make_notification(title=f"n{i}")

        second_page = self.client.get(self.list_url, {"page": 2}).data

        self.assertIsNone(second_page["next"])
        self.assertIsNotNone(second_page["previous"])