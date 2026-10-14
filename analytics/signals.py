import logging
from celery.signals import task_failure


logger = logging.getLogger(__name__)


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
