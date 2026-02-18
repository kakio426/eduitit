from django.core.management.base import BaseCommand, CommandError

from consent.schema import get_consent_schema_status


class Command(BaseCommand):
    help = "Validate required DB tables for consent service."

    def handle(self, *args, **options):
        is_ready, missing_tables, detail = get_consent_schema_status(force_refresh=True)
        if is_ready:
            self.stdout.write(self.style.SUCCESS("[consent] schema check passed"))
            return

        if detail:
            self.stdout.write(self.style.ERROR(f"[consent] schema check error: {detail}"))
        if missing_tables:
            self.stdout.write(self.style.ERROR("[consent] missing tables:"))
            for table_name in missing_tables:
                self.stdout.write(self.style.ERROR(f" - {table_name}"))

        raise CommandError("Consent schema is not ready. Run: python manage.py migrate signatures")
