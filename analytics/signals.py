import logging

from celery.signals import task_failure
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

ALERT_COOLDOWN_SECONDS = 15 * 60


@task_failure.connect
def log_celery_task_failure(sender=None,task_id=None,exception=None,args=None,kwargs=None,einfo=None,**extra,):
    
    task_name = getattr(sender, "name", "unknown")
    logger.error(
        "Celery task failed | task=%s | task_id=%s | error=%s",
        task_name,
        task_id,
        exception,
        exc_info=(
            (einfo.type, einfo.exception, einfo.tb)
            if einfo is not None
            else None
        ),
    )

    recipient = getattr(settings,"BACKBLOG_REPORT_RECIPIENT","",).strip()
    if not recipient:
        logger.warning(
            "Failure alert skipped: recipient is not configured."
        )
        return

    # Use the task name so repeated failures share one cooldown.
    cache_key = f"celery_failure_alert:{task_name}"

    try:
        should_send = cache.add(
            cache_key,
            task_id or "unknown",
            timeout=ALERT_COOLDOWN_SECONDS,
        )
    except Exception:
        logger.exception(
            "Could not access alert cooldown cache | task=%s",
            task_name,
        )

        # Redis may be unavailable. Attempt an alert anyway.
        # Deduplication cannot be guaranteed during this fallback.
        should_send = True

    if not should_send:
        logger.warning(
            "Failure alert suppressed by cooldown | task=%s | task_id=%s",
            task_name,
            task_id,
        )
        return

    subject = f"[BackBlog Alert] Celery task failed: {task_name}"
    message = (
        "A BackBlog background task has failed permanently.\n\n"
        f"Task: {task_name}\n"
        f"Task ID: {task_id}\n"
        f"Error: {exception}\n\n"
        "Check the Celery worker logs for the full traceback."
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
            # Permit a later failure to retry the alert.
            cache.delete(cache_key)
            logger.error(
                "Failure alert email was not sent | task_id=%s",
                task_id,
            )
            return

        logger.info(
            "Failure alert email sent | task=%s | task_id=%s",
            task_name,
            task_id,
        )

    except Exception:
        # Release the cooldown if delivery failed, so a later failure
        # can try again.
        try:
            cache.delete(cache_key)
        except Exception:
            logger.exception("Could not clear failed alert cooldown.")

        logger.exception(
            "Could not send failure alert email | task=%s | task_id=%s",
            task_name,
            task_id,
        )