from datetime import timedelta
import logging

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone

from version_manager.models import Document, DocumentVersion

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Delete document versions older than retention days (default: 30).'
    required_tables = {
        'version_manager_document',
        'version_manager_documentversion',
    }

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30, help='Retention days. Default is 30.')
        parser.add_argument('--dry-run', action='store_true', help='Show targets without deleting.')

    def _schema_ready(self):
        try:
            existing = set(connection.introspection.table_names())
        except Exception as e:
            self.stderr.write(
                self.style.WARNING(f'[delete_expired_versions] DB introspection failed: {e}')
            )
            return False

        missing = sorted(self.required_tables - existing)
        if missing:
            self.stderr.write(
                self.style.WARNING(
                    '[delete_expired_versions] skipped: required tables are missing '
                    f'({", ".join(missing)}). Run migrations in the same environment/DB first.'
                )
            )
            return False
        return True

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        cutoff = timezone.now() - timedelta(days=days)

        if not self._schema_ready():
            return

        targets = (
            DocumentVersion.objects
            .select_related('document')
            .filter(created_at__lt=cutoff)
            .order_by('created_at')
        )
        try:
            total = targets.count()
        except (OperationalError, ProgrammingError) as e:
            self.stderr.write(
                self.style.WARNING(
                    '[delete_expired_versions] skipped due to DB schema/query error. '
                    f'Run migrations first. detail={e}'
                )
            )
            return

        self.stdout.write(f'[delete_expired_versions] days={days}, cutoff={cutoff.isoformat()}, targets={total}')

        deleted_count = 0
        for version in targets:
            self.stdout.write(f'- target: document_id={version.document_id}, version=v{version.version:02d}, created_at={version.created_at}')
            if dry_run:
                continue

            try:
                if version.document.published_version_id == version.id:
                    Document.objects.filter(id=version.document_id).update(published_version=None)

                if version.upload:
                    # Cloudinary backend uses destroy API; local backend removes file in MEDIA_ROOT.
                    version.upload.delete(save=False)

                version.delete()
                deleted_count += 1
            except Exception as e:
                logger.error(
                    'Failed deleting document version (id=%s, document_id=%s, version=%s): %s',
                    version.id,
                    version.document_id,
                    version.version,
                    e,
                )

        if dry_run:
            self.stdout.write(self.style.WARNING(f'[DRY-RUN] {total} versions would be deleted.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'[DONE] Deleted {deleted_count} expired versions.'))
