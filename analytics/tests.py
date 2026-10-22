from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse, NoReverseMatch
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from blog.models import Post

from .models import AnalyticsEvent
from .services import record_event
from .tasks import (
    backblog_health_check,
    generate_daily_analytics_report,
    email_daily_analytics_report,
    monitor_scheduled_tasks,
    record_task_success,
)

VIEW = AnalyticsEvent.EventType.POST_VIEW
REACTION = AnalyticsEvent.EventType.REACTION
COMMENT = AnalyticsEvent.EventType.COMMENT
SHARE = AnalyticsEvent.EventType.SHARE
BOOKMARK = AnalyticsEvent.EventType.BOOKMARK
FOLLOW = AnalyticsEvent.EventType.FOLLOW
PUBLISHED = AnalyticsEvent.EventType.POST_PUBLISHED

LOCMEM_CACHE = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
}


# ============================================================
# HELPERS
# ============================================================
def url(name, **kwargs):
    """Reverse a URL, with or without the /api/<version>/ kwarg."""
    try:
        return reverse(name, kwargs={"version": "v1", **kwargs})
    except NoReverseMatch:
        return reverse(name, kwargs=kwargs)


class AnalyticsTestBase(APITestCase):
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

    def make_post(self, title="A post", published=True, **kwargs):
        if published:
            kwargs.setdefault("status", Post.Status.PUBLISHED)
        return Post.objects.create(
            author=self.author, title=title, content="Some content", **kwargs
        )

    def make_event(self, event_type=VIEW, post=None, actor=None, days_ago=0, **kwargs):
        event = AnalyticsEvent.objects.create(
            event_type=event_type, post=post, actor=actor, **kwargs
        )
        if days_ago:
            # occurred_at is auto_now_add, so move it back with update()
            AnalyticsEvent.objects.filter(pk=event.pk).update(
                occurred_at=timezone.now() - timedelta(days=days_ago)
            )
        return event

    def make_events(self, count, event_type=VIEW, post=None, days_ago=0):
        for _ in range(count):
            self.make_event(event_type, post=post, days_ago=days_ago)

    def setUp(self):
        self.admin = self.make_user(User.Role.ADMIN, "admin1")
        self.editor = self.make_user(User.Role.EDITOR, "editor1")
        self.author = self.make_user(User.Role.AUTHOR, "author1")
        self.subscriber = self.make_user(User.Role.SUBSCRIBER, "reader1")


# ============================================================
# MODEL + SERVICE
# ============================================================
class RecordEventServiceTests(AnalyticsTestBase):
    def test_record_event_creates_event(self):
        post = self.make_post()
        event = record_event(
            event_type=VIEW,
            actor=self.subscriber,
            post=post,
            source="homepage",
            metadata={"k": "v"},
        )
        self.assertEqual(event.event_type, VIEW)
        self.assertEqual(event.actor, self.subscriber)
        self.assertEqual(event.post, post)
        self.assertEqual(event.source, "homepage")
        self.assertEqual(event.metadata, {"k": "v"})

    def test_record_event_defaults(self):
        event = record_event(event_type=VIEW)
        self.assertIsNone(event.actor)
        self.assertIsNone(event.post)
        self.assertEqual(event.metadata, {})
        self.assertEqual(event.visitor_id, "")

    def test_record_event_rejects_unknown_type(self):
        with self.assertRaises(ValueError):
            record_event(event_type="not_a_real_type")
        self.assertEqual(AnalyticsEvent.objects.count(), 0)

    def test_deleting_post_keeps_event(self):
        post = self.make_post()
        event = self.make_event(post=post)
        post.delete()
        event.refresh_from_db()
        self.assertIsNone(event.post)

    def test_deleting_actor_keeps_event(self):
        event = self.make_event(actor=self.subscriber)
        self.subscriber.delete()
        event.refresh_from_db()
        self.assertIsNone(event.actor)


# ============================================================
# EVENTS ARE RECORDED BY OTHER APPS
# ============================================================
class EventRecordingTests(AnalyticsTestBase):
    def test_viewing_published_post_records_one_view(self):
        post = self.make_post()
        self.client.get(url("post-detail", post_id=post.id))

        events = AnalyticsEvent.objects.filter(event_type=VIEW)
        self.assertEqual(events.count(), 1)
        event = events.first()
        self.assertEqual(event.post, post)
        self.assertIsNone(event.actor)
        self.assertEqual(event.source, "post_detail")

    def test_logged_in_view_records_actor(self):
        post = self.make_post()
        self.client.force_authenticate(user=self.subscriber)
        self.client.get(url("post-detail", post_id=post.id))
        self.assertEqual(AnalyticsEvent.objects.get().actor, self.subscriber)

    def test_viewing_draft_records_nothing(self):
        post = self.make_post(published=False)
        response = self.client.get(url("post-detail", post_id=post.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(AnalyticsEvent.objects.count(), 0)


# ============================================================
# PERMISSIONS
# ============================================================
class AnalyticsPermissionTests(AnalyticsTestBase):
    ENDPOINTS = [
        "analytics-events",
        "analytics-summary",
        "analytics-top-viewed-posts",
        "analytics-top-engaged-posts",
        "analytics-traffic-trends",
    ]

    def test_anonymous_gets_401(self):
        for name in self.ENDPOINTS:
            with self.subTest(endpoint=name):
                response = self.client.get(url(name))
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_author_gets_403(self):
        self.client.force_authenticate(user=self.author)
        for name in self.ENDPOINTS:
            with self.subTest(endpoint=name):
                response = self.client.get(url(name))
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_subscriber_gets_403(self):
        self.client.force_authenticate(user=self.subscriber)
        for name in self.ENDPOINTS:
            with self.subTest(endpoint=name):
                response = self.client.get(url(name))
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_editor_gets_200(self):
        self.client.force_authenticate(user=self.editor)
        for name in self.ENDPOINTS:
            with self.subTest(endpoint=name):
                response = self.client.get(url(name))
                self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_gets_200(self):
        self.client.force_authenticate(user=self.admin)
        for name in self.ENDPOINTS:
            with self.subTest(endpoint=name):
                response = self.client.get(url(name))
                self.assertEqual(response.status_code, status.HTTP_200_OK)


# ============================================================
# EVENT LIST
# ============================================================
class EventListTests(AnalyticsTestBase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.editor)
        self.events_url = url("analytics-events")

    def test_list_has_pagination_envelope(self):
        self.make_event()
        response = self.client.get(self.events_url)
        for key in ("count", "next", "previous", "results"):
            self.assertIn(key, response.data)

    def test_list_returns_events_newest_first(self):
        old = self.make_event(days_ago=3)
        new = self.make_event()
        response = self.client.get(self.events_url)
        ids = [str(e["id"]) for e in response.data["results"]]
        self.assertEqual(ids, [str(new.id), str(old.id)])

    def test_event_shows_actor_email_and_post_title(self):
        post = self.make_post("Hello")
        self.make_event(post=post, actor=self.subscriber)
        item = self.client.get(self.events_url).data["results"][0]
        self.assertEqual(item["actor_email"], self.subscriber.email)
        self.assertEqual(item["post_title"], "Hello")

    def test_anonymous_event_has_null_actor_email(self):
        self.make_event()
        item = self.client.get(self.events_url).data["results"][0]
        self.assertIsNone(item["actor_email"])
        self.assertIsNone(item["post_title"])

    def test_filter_by_type(self):
        self.make_event(VIEW)
        self.make_event(REACTION)
        response = self.client.get(self.events_url, {"type": "reaction"})
        types = [e["event_type"] for e in response.data["results"]]
        self.assertEqual(types, ["reaction"])

    def test_invalid_type_is_400(self):
        response = self.client.get(self.events_url, {"type": "bogus"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_start_date_is_400(self):
        response = self.client.get(self.events_url, {"start_date": "not-a-date"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_end_date_is_400(self):
        response = self.client.get(self.events_url, {"end_date": "2026-13-45"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_start_after_end_is_400(self):
        response = self.client.get(
            self.events_url, {"start_date": "2026-10-20", "end_date": "2026-10-01"}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_start_date_filter(self):
        today = timezone.localdate()
        self.make_event(days_ago=0)
        self.make_event(days_ago=10)
        response = self.client.get(
            self.events_url, {"start_date": (today - timedelta(days=2)).isoformat()}
        )
        self.assertEqual(response.data["count"], 1)

    def test_end_date_filter(self):
        today = timezone.localdate()
        self.make_event(days_ago=0)
        self.make_event(days_ago=10)
        response = self.client.get(
            self.events_url, {"end_date": (today - timedelta(days=5)).isoformat()}
        )
        self.assertEqual(response.data["count"], 1)

    def test_events_are_read_only(self):
        for method in (self.client.post, self.client.put, self.client.delete):
            with self.subTest(method=method):
                response = method(self.events_url, {}, format="json")
                self.assertEqual(
                    response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED
                )


# ============================================================
# SUMMARY
# ============================================================
class SummaryTests(AnalyticsTestBase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.editor)
        self.summary_url = url("analytics-summary")

    def test_empty_summary_is_all_zeros(self):
        data = self.client.get(self.summary_url).data
        self.assertEqual(data["total_events"], 0)
        self.assertEqual(data["events_today"], 0)
        self.assertEqual(data["post_views"], 0)
        self.assertEqual(data["activity_breakdown"], [])

    def test_summary_counts(self):
        self.make_events(2, VIEW)
        self.make_event(REACTION)
        self.make_event(COMMENT)
        self.make_event(SHARE)
        self.make_event(BOOKMARK)
        self.make_event(FOLLOW)
        self.make_event(PUBLISHED)
        self.make_event(VIEW, days_ago=3)

        data = self.client.get(self.summary_url).data

        self.assertEqual(data["total_events"], 9)
        self.assertEqual(data["events_today"], 8)
        self.assertEqual(data["post_views"], 3)
        self.assertEqual(data["reactions"], 1)
        self.assertEqual(data["comments"], 1)
        self.assertEqual(data["shares"], 1)
        self.assertEqual(data["bookmarks"], 1)
        self.assertEqual(data["follows"], 1)
        self.assertEqual(data["post_publications"], 1)

    def test_breakdown_is_sorted_by_total(self):
        self.make_events(3, VIEW)
        self.make_event(REACTION)
        breakdown = self.client.get(self.summary_url).data["activity_breakdown"]
        self.assertEqual(breakdown[0], {"event_type": "post_view", "total": 3})
        self.assertEqual(breakdown[1], {"event_type": "reaction", "total": 1})


# ============================================================
# TOP VIEWED / TOP ENGAGED
# ============================================================
class TopPostsTests(AnalyticsTestBase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.editor)

    def test_top_viewed_orders_by_views(self):
        a = self.make_post("Post A")
        b = self.make_post("Post B")
        self.make_events(3, VIEW, post=a)
        self.make_events(1, VIEW, post=b)

        data = self.client.get(url("analytics-top-viewed-posts")).data

        self.assertEqual(data["count"], 2)
        self.assertEqual([r["title"] for r in data["results"]], ["Post A", "Post B"])
        self.assertEqual([r["total_views"] for r in data["results"]], [3, 1])
        self.assertEqual(str(data["results"][0]["post_id"]), str(a.id))
        self.assertEqual(data["results"][0]["slug"], a.slug)

    def test_top_viewed_ignores_other_events_and_null_posts(self):
        a = self.make_post("Post A")
        self.make_event(VIEW, post=a)
        self.make_event(REACTION, post=a)
        self.make_event(VIEW, post=None)

        data = self.client.get(url("analytics-top-viewed-posts")).data

        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["total_views"], 1)

    def test_top_viewed_is_limited_to_ten(self):
        for i in range(12):
            self.make_event(VIEW, post=self.make_post(f"Post {i}"))
        data = self.client.get(url("analytics-top-viewed-posts")).data
        self.assertEqual(data["count"], 10)

    def test_top_engaged_counts_only_engagement_events(self):
        a = self.make_post("Post A")
        b = self.make_post("Post B")
        for kind in (REACTION, COMMENT, SHARE, BOOKMARK):
            self.make_event(kind, post=a)
        self.make_events(5, VIEW, post=a)  # views must not count
        self.make_event(REACTION, post=b)

        data = self.client.get(url("analytics-top-engaged-posts")).data

        self.assertEqual([r["title"] for r in data["results"]], ["Post A", "Post B"])
        self.assertEqual([r["total_engagements"] for r in data["results"]], [4, 1])

    def test_top_engaged_ignores_posts_with_only_views(self):
        a = self.make_post("Post A")
        self.make_events(3, VIEW, post=a)
        data = self.client.get(url("analytics-top-engaged-posts")).data
        self.assertEqual(data["count"], 0)


# ============================================================
# TRAFFIC TRENDS
# ============================================================
class TrafficTrendsTests(AnalyticsTestBase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.editor)
        self.trends_url = url("analytics-traffic-trends")

    def test_default_range_is_last_seven_days(self):
        today = timezone.localdate()
        data = self.client.get(self.trends_url).data
        self.assertEqual(data["days"], 7)
        self.assertEqual(len(data["results"]), 7)
        self.assertEqual(data["results"][0]["date"], (today - timedelta(days=6)).isoformat())
        self.assertEqual(data["results"][-1]["date"], today.isoformat())

    def test_days_without_events_are_zero_filled(self):
        data = self.client.get(self.trends_url).data
        for row in data["results"]:
            self.assertEqual(row["total_events"], 0)
            self.assertEqual(row["post_views"], 0)
            self.assertEqual(row["engagements"], 0)

    def test_today_counts(self):
        self.make_events(2, VIEW)
        self.make_event(REACTION)
        today_row = self.client.get(self.trends_url).data["results"][-1]
        self.assertEqual(today_row["total_events"], 3)
        self.assertEqual(today_row["post_views"], 2)
        self.assertEqual(today_row["engagements"], 1)

    def test_events_land_on_the_right_day(self):
        self.make_event(VIEW, days_ago=2)
        results = self.client.get(self.trends_url).data["results"]
        self.assertEqual(results[-3]["post_views"], 1)
        self.assertEqual(results[-1]["post_views"], 0)

    def test_custom_range(self):
        today = timezone.localdate()
        response = self.client.get(
            self.trends_url,
            {
                "start_date": (today - timedelta(days=2)).isoformat(),
                "end_date": today.isoformat(),
            },
        )
        self.assertEqual(response.data["days"], 3)

    def test_invalid_start_date_is_400(self):
        response = self.client.get(self.trends_url, {"start_date": "nope"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_end_date_is_400(self):
        response = self.client.get(self.trends_url, {"end_date": "nope"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_start_after_end_is_400(self):
        today = timezone.localdate()
        response = self.client.get(
            self.trends_url,
            {
                "start_date": today.isoformat(),
                "end_date": (today - timedelta(days=1)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_366_day_range_is_allowed(self):
        today = timezone.localdate()
        response = self.client.get(
            self.trends_url, {"start_date": (today - timedelta(days=365)).isoformat()}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["days"], 366)

    def test_367_day_range_is_rejected(self):
        today = timezone.localdate()
        response = self.client.get(
            self.trends_url, {"start_date": (today - timedelta(days=366)).isoformat()}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_impossible_calendar_date_is_400(self):
        response = self.client.get(self.trends_url, {"start_date": "2026-02-30"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

# ============================================================
# TRENDING POSTS (public)
# ============================================================
class TrendingPostsTests(AnalyticsTestBase):
    def setUp(self):
        super().setUp()
        self.trending_url = url("analytics-trending-posts")

    def test_anonymous_can_read_trending(self):
        response = self.client.get(self.trending_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])

    def test_posts_are_ranked_by_weighted_score(self):
        a = self.make_post("Post A")
        b = self.make_post("Post B")
        self.make_events(3, VIEW, post=a)  # score 3
        self.make_event(COMMENT, post=b)  # score 4

        data = self.client.get(self.trending_url).data

        self.assertEqual([r["title"] for r in data["results"]], ["Post B", "Post A"])
        self.assertEqual([r["trending_score"] for r in data["results"]], [4, 3])

    def test_score_weights(self):
        post = self.make_post()
        for kind in (VIEW, REACTION, COMMENT, SHARE, BOOKMARK):
            self.make_event(kind, post=post)

        item = self.client.get(self.trending_url).data["results"][0]

        # 1 (view) + 3 (reaction) + 4 (comment) + 3 (share) + 2 (bookmark)
        self.assertEqual(item["trending_score"], 13)
        self.assertEqual(item["recent_views"], 1)
        self.assertEqual(item["recent_reactions"], 1)
        self.assertEqual(item["recent_comments"], 1)
        self.assertEqual(item["recent_shares"], 1)
        self.assertEqual(item["recent_bookmarks"], 1)

    def test_unpublished_posts_are_excluded(self):
        draft = self.make_post("Draft", published=False)
        self.make_events(5, VIEW, post=draft)
        self.assertEqual(self.client.get(self.trending_url).data["count"], 0)

    def test_private_posts_are_excluded(self):
        private = self.make_post("Private", visibility=Post.Visibility.PRIVATE)
        self.make_events(5, VIEW, post=private)
        self.assertEqual(self.client.get(self.trending_url).data["count"], 0)

    def test_posts_without_events_are_excluded(self):
        self.make_post("Quiet")
        self.assertEqual(self.client.get(self.trending_url).data["count"], 0)

    def test_follow_events_do_not_count(self):
        post = self.make_post()
        self.make_event(FOLLOW, post=post)
        self.assertEqual(self.client.get(self.trending_url).data["count"], 0)

    def test_old_events_are_ignored_by_default(self):
        post = self.make_post()
        self.make_event(VIEW, post=post, days_ago=10)
        self.assertEqual(self.client.get(self.trending_url).data["count"], 0)

    def test_days_parameter_widens_the_window(self):
        post = self.make_post()
        self.make_event(VIEW, post=post, days_ago=10)
        response = self.client.get(self.trending_url, {"days": 30})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["period_days"], 30)

    def test_invalid_days_values_are_rejected(self):
        for value in ("abc", "0", "31", "-1"):
            with self.subTest(days=value):
                response = self.client.get(self.trending_url, {"days": value})
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_result_is_limited_to_ten(self):
        for i in range(12):
            self.make_event(VIEW, post=self.make_post(f"Post {i}"))
        self.assertEqual(self.client.get(self.trending_url).data["count"], 10)

    def test_trending_does_not_return_full_content_or_email(self):
        post = self.make_post()
        self.make_event(VIEW, post=post)
        item = self.client.get(self.trending_url).data["results"][0]
        self.assertNotIn("content", item)
        self.assertNotEqual(item["author"], self.author.email)


# ============================================================
# CELERY TASK STATUS ENDPOINT (admin only)
# ============================================================
class CeleryTaskStatusTests(AnalyticsTestBase):
    def setUp(self):
        super().setUp()
        self.status_url = url("analytics-task-status")

    def test_anonymous_gets_401(self):
        response = self.client.get(self.status_url, {"task_id": "abc"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_editor_gets_403(self):
        self.client.force_authenticate(user=self.editor)
        response = self.client.get(self.status_url, {"task_id": "abc"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_task_id_is_400(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.status_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("analytics.views.AsyncResult")
    def test_success_result_is_filtered(self, mock_result):
        task = mock_result.return_value
        task.status = "SUCCESS"
        task.ready.return_value = True
        task.result = {
            "status": "success",
            "recipient": "ops@example.com",
            "secret": "must-not-leak",
            "nested": {"a": 1},
        }
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.status_url, {"task_id": "abc"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "SUCCESS")
        self.assertTrue(response.data["ready"])
        self.assertEqual(response.data["result"]["recipient"], "ops@example.com")
        self.assertNotIn("secret", response.data["result"])
        self.assertNotIn("nested", response.data["result"])

    @patch("analytics.views.AsyncResult")
    def test_non_dict_result_is_not_exposed(self, mock_result):
        task = mock_result.return_value
        task.status = "SUCCESS"
        task.ready.return_value = True
        task.result = "some raw value"
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.status_url, {"task_id": "abc"})

        self.assertEqual(response.data["result"], {"available": True})

    @patch("analytics.views.AsyncResult")
    def test_failed_task_does_not_expose_result(self, mock_result):
        task = mock_result.return_value
        task.status = "FAILURE"
        task.ready.return_value = True
        task.result = Exception("traceback details")
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.status_url, {"task_id": "abc"})

        self.assertEqual(response.data["status"], "FAILURE")
        self.assertNotIn("result", response.data)

    @patch("analytics.views.AsyncResult")
    def test_pending_task_has_no_result(self, mock_result):
        task = mock_result.return_value
        task.status = "PENDING"
        task.ready.return_value = False
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.status_url, {"task_id": "abc"})

        self.assertFalse(response.data["ready"])
        self.assertNotIn("result", response.data)


# ============================================================
# CELERY TASKS (called directly, no broker needed)
# ============================================================
@override_settings(
    CACHES=LOCMEM_CACHE,
    BACKBLOG_REPORT_RECIPIENT="ops@example.com",
    DEFAULT_FROM_EMAIL="noreply@example.com",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class TaskTests(AnalyticsTestBase):
    def setUp(self):
        super().setUp()
        cache.clear()

    # ----- health check -----
    def test_health_check_returns_success_and_records_it(self):
        result = backblog_health_check()
        self.assertEqual(result["status"], "success")
        self.assertIsNotNone(cache.get("backblog_task_last_success:health_check"))

    # ----- daily report -----
    def test_daily_report_compares_yesterday_with_previous_day(self):
        today = timezone.localdate()
        self.make_events(2, VIEW, days_ago=1)
        self.make_events(1, VIEW, days_ago=2)
        self.make_events(4, VIEW, days_ago=0)  # today is not part of the report

        report = generate_daily_analytics_report()

        self.assertEqual(report["status"], "success")
        self.assertEqual(report["report_date"], (today - timedelta(days=1)).isoformat())
        self.assertEqual(
            report["metrics"]["post_view"],
            {"total": 2, "previous_total": 1, "change": 1},
        )

    def test_daily_report_includes_every_event_type(self):
        report = generate_daily_analytics_report()
        expected = {value for value, _ in AnalyticsEvent.EventType.choices}
        self.assertEqual(set(report["metrics"]), expected)

    # ----- emailed report -----
    def test_email_report_is_sent_to_recipient(self):
        self.make_events(1, VIEW, days_ago=1)

        result = email_daily_analytics_report()

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ops@example.com"])
        self.assertIn(result["report_date"], mail.outbox[0].subject)
        self.assertIn("post_view", mail.outbox[0].body)
        self.assertIsNotNone(
            cache.get("backblog_task_last_success:daily_analytics_report")
        )

    @override_settings(BACKBLOG_REPORT_RECIPIENT="")
    def test_email_report_without_recipient_fails(self):
        with self.assertRaises(ValueError):
            email_daily_analytics_report()
        self.assertEqual(len(mail.outbox), 0)

    # ----- monitor -----
    def test_monitor_flags_tasks_that_never_ran(self):
        result = monitor_scheduled_tasks()

        self.assertEqual(result["status"], "warning")
        self.assertIn("BackBlog Health Check", result["overdue_tasks"])
        self.assertTrue(result["alert_sent"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ops@example.com"])

    def test_monitor_flags_stale_health_check(self):
        cache.set(
            "backblog_task_last_success:health_check",
            (timezone.now() - timedelta(minutes=10)).isoformat(),
        )
        record_task_success("daily_analytics_report")

        result = monitor_scheduled_tasks()

        self.assertEqual(result["overdue_tasks"], ["BackBlog Health Check"])

    def test_monitor_is_quiet_when_everything_is_fresh(self):
        record_task_success("health_check")
        record_task_success("daily_analytics_report")

        result = monitor_scheduled_tasks()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["overdue_tasks"], [])
        self.assertEqual(len(mail.outbox), 0)

    def test_monitor_alert_has_a_cooldown(self):
        first = monitor_scheduled_tasks()
        second = monitor_scheduled_tasks()

        self.assertTrue(first["alert_sent"])
        self.assertFalse(second["alert_sent"])
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(BACKBLOG_REPORT_RECIPIENT="")
    def test_monitor_without_recipient_sends_nothing(self):
        result = monitor_scheduled_tasks()
        self.assertFalse(result["alert_sent"])
        self.assertEqual(len(mail.outbox), 0)


# ============================================================
# KNOWN PROBLEMS
# These are expected to FAIL until the bugs are fixed.
# ============================================================
class KnownIssueTests(AnalyticsTestBase):
    def test_publishing_a_post_records_post_published_event(self):
        post = self.make_post(published=False, status=Post.Status.APPROVED)
        self.client.force_authenticate(user=self.editor)

        response = self.client.post(
            url("post-publish", post_id=post.id), {"action": "publish"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            AnalyticsEvent.objects.filter(event_type=PUBLISHED, post=post).count(), 1
        )

    @patch("blog.views.record_event", side_effect=Exception("analytics down"))
    def test_analytics_failure_does_not_break_post_detail(self, _mock):
        self.client.raise_request_exception = False
        post = self.make_post()

        response = self.client.get(url("post-detail", post_id=post.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)