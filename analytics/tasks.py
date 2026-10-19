from django.core.mail import send_mail
from django.conf import settings
from django.core.cache import cache
from datetime import timedelta
from django.utils.dateparse import parse_datetime
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

    record_task_success("health_check")

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
        record_task_success("daily_analytics_report")

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

# ======================
# RECORD TASK SUCCESS
# ======================
def record_task_success(task_name):
    """Store the last successful execution time in Redis."""
    cache.set(
        f"backblog_task_last_success:{task_name}",
        timezone.now().isoformat(),
        timeout=None,
    )

# ======================
# MONITOR SCHEDULED
# ======================
@shared_task
def monitor_scheduled_tasks():
    """
    Detect scheduled tasks that have not completed successfully
    within their expected execution windows.
    """
    now = timezone.now()
    local_now = timezone.localtime(now)

    monitored_tasks = {
        "health_check": {
            "label": "BackBlog Health Check",
            "max_age": timedelta(minutes=5),
        },
        "daily_analytics_report": {
            "label": "BackBlog Daily Analytics Report",
            "max_age": None,
        },
    }

    overdue = []

    for task_key, config in monitored_tasks.items():
        last_success = cache.get(
            f"backblog_task_last_success:{task_key}"
        )

        # The daily report has a fixed daily deadline:
        # 00:15 Africa/Lagos.
        if task_key == "daily_analytics_report":
            deadline_passed = (
                local_now.hour > 0
                or (local_now.hour == 0 and local_now.minute >= 15)
            )

            if not deadline_passed:
                continue

            # A report completed today means the daily run succeeded.
            if last_success:
                last_success_dt = parse_datetime(last_success)

                if (
                    last_success_dt
                    and timezone.localtime(last_success_dt).date()
                    == local_now.date()
                ):
                    continue

            overdue.append(config["label"])
            continue

        if not last_success:
            overdue.append(config["label"])
            continue

        last_success_dt = parse_datetime(last_success)

        if not last_success_dt:
            logger.warning(
                "Invalid success timestamp for monitored task: %s",
                task_key,
            )
            overdue.append(config["label"])
            continue

        if now - last_success_dt > config["max_age"]:
            overdue.append(config["label"])

    if not overdue:
        logger.info("Scheduled-task monitor: all monitored tasks are healthy.")
        return {
            "status": "success",
            "overdue_tasks": [],
            "checked_at": now.isoformat(),
        }

    logger.error("Scheduled tasks overdue: %s",", ".join(overdue),)
    alert_sent = send_missed_task_alert(overdue)

    return {
        "status": "warning",
        "overdue_tasks": overdue,
        "alert_sent": alert_sent,
        "checked_at": now.isoformat(),
    }

# ======================
# SEND MISSED TASKS
# ======================
def send_missed_task_alert(overdue_tasks):
    """Email an alert when scheduled tasks are overdue."""
    recipient = getattr(
        settings,
        "BACKBLOG_REPORT_RECIPIENT",
        "",
    ).strip()

    if not recipient:
        logger.warning(
            "Missed-task alert skipped: recipient is not configured."
        )
        return False

    cache_key = "backblog_missed_task_alert_cooldown"

    # Send at most one alert every 15 minutes.
    if not cache.add(cache_key, True, timeout=15 * 60):
        logger.warning(
            "Missed-task alert suppressed by cooldown."
        )
        return False

    subject = "[BackBlog Alert] Scheduled task overdue"

    message = (
        "BackBlog has detected scheduled tasks that are overdue.\n\n"
        "Overdue tasks:\n"
        + "\n".join(f"- {task}" for task in overdue_tasks)
        + "\n\nPlease check the Celery worker and Beat logs."
    )

    try:
        sent = send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )

        if sent != 1:
            cache.delete(cache_key)
            logger.error("Missed-task alert email was not sent.")
            return False

        logger.info(
            "Missed-task alert email sent to %s.",
            recipient,
        )
        return True

    except Exception:
        cache.delete(cache_key)
        logger.exception("Failed to send missed-task alert.")
        return False