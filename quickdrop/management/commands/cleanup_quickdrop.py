from django.core.management.base import BaseCommand

from quickdrop.services import cleanup_stale_activity


class Command(BaseCommand):
    help = "Delete yesterday quickdrop history and clear stale current state"

    def handle(self, *args, **options):
        cleaned = cleanup_stale_activity()
        self.stdout.write(self.style.SUCCESS(f"cleanup_quickdrop completed ({cleaned} items cleared)"))
