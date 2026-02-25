from django.apps import AppConfig


class HandoffConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "handoff"
    verbose_name = "배부 체크"
