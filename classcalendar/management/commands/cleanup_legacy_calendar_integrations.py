from django.core.management.base import BaseCommand

from classcalendar.integrations import (
    SOURCE_COLLECT_DEADLINE,
    SOURCE_CONSENT_EXPIRY,
    SOURCE_RESERVATION,
    SOURCE_SIGNATURES_TRAINING,
)
from classcalendar.models import CalendarEvent


LEGACY_SOURCES = (
    SOURCE_COLLECT_DEADLINE,
    SOURCE_CONSENT_EXPIRY,
    SOURCE_RESERVATION,
    SOURCE_SIGNATURES_TRAINING,
)


class Command(BaseCommand):
    help = "Delete locked legacy integration calendar events that are now served directly from source services."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many legacy rows would be deleted without removing them.",
        )
        parser.add_argument(
            "--user-id",
            type=int,
            default=0,
            help="Restrict cleanup to a single author id.",
        )

    def handle(self, *args, **options):
        queryset = CalendarEvent.objects.filter(
            is_locked=True,
            integration_source__in=LEGACY_SOURCES,
        )
        user_id = int(options.get("user_id") or 0)
        if user_id > 0:
            queryset = queryset.filter(author_id=user_id)

        total = queryset.count()
        if options.get("dry_run"):
            self.stdout.write(self.style.WARNING(f"dry-run: {total} legacy integration events would be deleted."))
            return

        deleted_count, _ = queryset.delete()
        self.stdout.write(self.style.SUCCESS(f"deleted {deleted_count} rows from {total} legacy integration events."))
