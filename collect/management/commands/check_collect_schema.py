from django.core.management.base import BaseCommand, CommandError

from collect.schema import get_collect_schema_status


class Command(BaseCommand):
    help = "Validate required DB columns for collect service."

    def handle(self, *args, **options):
        is_ready, missing_tables, missing_columns, detail = get_collect_schema_status(force_refresh=True)
        if is_ready:
            self.stdout.write(self.style.SUCCESS("[collect] schema check passed"))
            return

        if detail:
            self.stdout.write(self.style.ERROR(f"[collect] schema check error: {detail}"))
        if missing_tables:
            self.stdout.write(self.style.ERROR("[collect] missing tables:"))
            for table_name in missing_tables:
                self.stdout.write(self.style.ERROR(f" - {table_name}"))
        if missing_columns:
            self.stdout.write(self.style.ERROR("[collect] missing columns:"))
            for table_name, columns in missing_columns.items():
                joined = ", ".join(columns)
                self.stdout.write(self.style.ERROR(f" - {table_name}: {joined}"))

        raise CommandError("Collect schema is not ready. Run: python manage.py migrate collect")
