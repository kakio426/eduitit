from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS, connections
from django.db import OperationalError, ProgrammingError
from django.db.migrations.executor import MigrationExecutor

from quickdrop.services import cleanup_stale_activity


class Command(BaseCommand):
    help = "Delete yesterday quickdrop history and clear stale current state"

    def _has_pending_migrations(self) -> bool:
        connection = connections[DEFAULT_DB_ALIAS]
        executor = MigrationExecutor(connection)
        targets = executor.loader.graph.leaf_nodes()
        return bool(executor.migration_plan(targets))

    def handle(self, *args, **options):
        try:
            if self._has_pending_migrations():
                self.stdout.write(self.style.WARNING("cleanup_quickdrop skipped (pending migrations)"))
                return
        except (OperationalError, ProgrammingError) as exc:
            self.stdout.write(self.style.WARNING(f"cleanup_quickdrop skipped ({exc})"))
            return

        try:
            cleaned = cleanup_stale_activity()
        except (OperationalError, ProgrammingError) as exc:
            self.stdout.write(self.style.WARNING(f"cleanup_quickdrop skipped ({exc})"))
            return

        self.stdout.write(self.style.SUCCESS(f"cleanup_quickdrop completed ({cleaned} items cleared)"))
