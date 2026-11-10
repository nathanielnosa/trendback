from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from analytics.models import AnalyticsEvent
from analytics.services import record_event
from blog.models import Post
from notifications.services import notify_post_published


class Command(BaseCommand):
    """
    Publish approved posts whose scheduled time has arrived.

        python manage.py publish_scheduled

    Run it every minute or so from a scheduler (cron on Linux, Task Scheduler on
    Windows). Running it more often than needed is harmless: a post is only
    published once.
    """

    help = "Publish approved posts whose scheduled time has arrived."

    # ::: find the posts that are due and publish each one
    def handle(self, *args, **options):
        now = timezone.now()
        due_ids = list(
            Post.objects.filter(
                status=Post.Status.APPROVED,
                scheduled_at__isnull=False,
                scheduled_at__lte=now,
            ).values_list("id", flat=True)
        )

        published = 0
        for post_id in due_ids:
            if self.publish(post_id, now):
                published += 1

        self.stdout.write(self.style.SUCCESS(f"Published {published} scheduled post(s)."))

    # ::: publish one post; returns False if someone else already did
    def publish(self, post_id, now):
        with transaction.atomic():
            # Lock the row so two runs at the same time cannot both publish it.
            post = (
                Post.objects.select_for_update()
                .filter(id=post_id, status=Post.Status.APPROVED, scheduled_at__isnull=False)
                .first()
            )
            if post is None:
                return False

            post.status = Post.Status.PUBLISHED
            post.published_at = now
            post.scheduled_at = None
            post.save(update_fields=["status", "published_at", "scheduled_at", "updated_at"])

        # Side effects happen after the save, and must never undo the publishing.
        try:
            record_event(
                event_type=AnalyticsEvent.EventType.POST_PUBLISHED,
                actor=None,
                post=post,
                source="scheduled_publish",
            )
            notify_post_published(post, None)
        except Exception:
            self.stderr.write(f"Published {post.slug}, but could not record its events.")
        return True