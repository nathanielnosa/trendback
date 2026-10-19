from django_celery_beat.schedulers import DatabaseScheduler


class BackBlogDatabaseScheduler(DatabaseScheduler):
    """
    Load all enabled periodic tasks.

    Let Celery Beat handle due-time calculations rather than
    excluding tasks based on their scheduled hour.
    """

    def enabled_models_qs(self):
        return self.Model.objects.enabled()