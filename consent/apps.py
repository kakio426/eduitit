from django.apps import AppConfig


class ConsentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "consent"

    def ready(self):
        from . import signals  # noqa: F401
