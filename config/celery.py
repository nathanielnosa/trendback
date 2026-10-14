import os

from celery import Celery
from celery.signals import worker_init

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("backblog")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@worker_init.connect
def register_backblog_task_signals(**kwargs):
    from analytics import signals  # noqa: F401
