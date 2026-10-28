from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        # Registers the API documentation details used by /api/docs/
        from . import api_docs  # noqa: F401