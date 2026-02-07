import logging
from django.core.management.base import BaseCommand
from django.core.management import call_command

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'DB 백업 실행 (django-dbbackup 래핑)'

    def handle(self, *args, **options):
        self.stdout.write('DB 백업을 시작합니다...')
        try:
            call_command('dbbackup', '--clean')
            self.stdout.write(self.style.SUCCESS('DB 백업이 성공적으로 완료되었습니다.'))
            logger.info('DB backup completed successfully.')
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'DB 백업 실패: {e}'))
            logger.error(f'DB backup failed: {e}', exc_info=True)
            raise
