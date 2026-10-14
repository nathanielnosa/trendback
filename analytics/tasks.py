
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


class TemporaryTaskError(Exception):
    """Raised when a task encounters a temporary problem."""


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
