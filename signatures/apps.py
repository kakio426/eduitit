from django.apps import AppConfig


class SignaturesConfig(AppConfig):
    name = 'signatures'
    verbose_name = '잇티하게 서명 톡'

    def ready(self):
        from . import signals  # noqa: F401
