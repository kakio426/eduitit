from django.core.management.base import BaseCommand

from quickdrop.services import cleanup_expired_sessions


class Command(BaseCommand):
    help = "End idle quickdrop sessions and delete their temporary payloads"

    def handle(self, *args, **options):
        cleaned = cleanup_expired_sessions()
        self.stdout.write(self.style.SUCCESS(f"cleanup_quickdrop completed ({cleaned} sessions ended)"))
