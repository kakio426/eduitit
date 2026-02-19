from django.apps import AppConfig


class CollectConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "collect"
    verbose_name = "간편 수합"

    def ready(self):
        from . import signals  # noqa: F401