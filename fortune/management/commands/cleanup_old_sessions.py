import logging
import sys

from django.core.management.base import BaseCommand
from django.utils import timezone
from fortune.models import FortunePseudonymousCache

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Deletes expired fortune pseudonymous caches'

    def handle(self, *args, **options):
        try:
            now = timezone.now()
            expired_caches = FortunePseudonymousCache.objects.filter(expires_at__lt=now)

            deleted_caches, _ = expired_caches.delete()

            if deleted_caches:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully deleted {deleted_caches} expired pseudonymous caches.'
                    )
                )
            else:
                self.stdout.write(self.style.SUCCESS('No expired fortune pseudonymous caches found.'))
        except Exception as e:
            logger.error('Failed to cleanup expired fortune data: %s', e, exc_info=True)
            sys.exit(1)
