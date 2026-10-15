from datetime import timedelta
import logging

from celery import shared_task
from django.db.models import Count
from django.utils import timezone

from .models import AnalyticsEvent

import os

from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


class TemporaryTaskError(Exception):
    """Raised when a task encounters a temporary problem."""

# ======================
# backlog health check
# ======================
@shared_task
def backblog_health_check():
    logger.info("BackBlog health-check task started.")

    result = {
        "status": "success",
        "message": "BackBlog background task executed successfully.",
        "executed_at": timezone.now().isoformat(),
    }

    logger.info("BackBlog health-check task completed.")
    return result

# ======================
# backlog demo
# ======================
@shared_task(bind=True, max_retries=3, default_retry_delay=2)
def backblog_retry_demo(self, failures_before_success=2):
    logger.info("Retry demo started. Attempt: %s",self.request.retries + 1,)

    if self.request.retries < failures_before_success:
        error = TemporaryTaskError("Simulated temporary failure.")
        logger.warning("Temporary failure encountered. Retry attempt: %s",self.request.retries + 1,)

        raise self.retry(exc=error,countdown=2,)

    logger.info("Retry demo completed successfully.")

    return {
        "status": "success",
        "message": "Task recovered after temporary failures.",
        "retry_attempts": self.request.retries,
        "executed_at": timezone.now().isoformat(),
    }

# ======================
# generating daily analytics
# ======================
@shared_task
def generate_daily_analytics_report():
    """
    Generate an analytics summary for yesterday
    and compare it with the previous day.
    """
    today = timezone.localdate()
    report_date = today - timedelta(days=1)
    previous_date = report_date - timedelta(days=1)

    def get_event_counts(target_date):
        events = (
            AnalyticsEvent.objects
            .filter(occurred_at__date=target_date)
            .values("event_type")
            .annotate(total=Count("id"))
        )

        return {
            item["event_type"]: item["total"]
            for item in events
        }

    current_counts = get_event_counts(report_date)
    previous_counts = get_event_counts(previous_date)

    event_types = [
        event_type
        for event_type, _ in AnalyticsEvent.EventType.choices
    ]

    metrics = {}

    for event_type in event_types:
        current_total = current_counts.get(event_type, 0)
        previous_total = previous_counts.get(event_type, 0)

        metrics[event_type] = {
            "total": current_total,
            "previous_total": previous_total,
            "change": current_total - previous_total,
        }

    report = {
        "status": "success",
        "report_date": report_date.isoformat(),
        "compared_with": previous_date.isoformat(),
        "generated_at": timezone.now().isoformat(),
        "metrics": metrics,
    }

    logger.info("BackBlog daily analytics report: %s", report)

    return report

# ======================
# EMAIL DAILY REPORT
# ======================
@shared_task(bind=True,max_retries=3,default_retry_delay=60,)
def email_daily_analytics_report(self):
    """Generate and email the daily analytics report."""
    try:
        report = generate_daily_analytics_report()

        recipient = settings.BACKBLOG_REPORT_RECIPIENT
        if not recipient:
            raise ValueError(
                "BACKBLOG_REPORT_RECIPIENT is not configured."
            )

        metrics = report["metrics"]

        lines = [
            "BackBlog Daily Analytics Report",
            "",
            f"Report date: {report['report_date']}",
            f"Compared with: {report['compared_with']}",
            "",
            "Activity summary:",
        ]

        for event_type, values in metrics.items():
            lines.append(
                f"- {event_type}: {values['total']} "
                f"(previous: {values['previous_total']}, "
                f"change: {values['change']:+})"
            )

        lines.extend([
            "",
            f"Generated at: {report['generated_at']}",
        ])

        sent = send_mail(
            subject=f"BackBlog Daily Analytics — {report['report_date']}",
            message="\n".join(lines),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )

        if sent != 1:
            raise RuntimeError("The analytics report email was not sent.")

        logger.info(
            "Daily analytics report emailed successfully to %s",
            recipient,
        )

        return {
            "status": "success",
            "recipient": recipient,
            "report_date": report["report_date"],
        }

    except Exception as exc:
        logger.exception("Failed to email the daily analytics report.")
        raise self.retry(exc=exc)