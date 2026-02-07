import os
import logging
from datetime import datetime
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management import call_command

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'DB 백업 실행 (Django dumpdata 사용, pg_dump 불필요)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep', type=int, default=5,
            help='보관할 최대 백업 파일 수 (기본: 5)',
        )

    def handle(self, *args, **options):
        backup_dir = settings.BASE_DIR / 'backups'
        backup_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = backup_dir / f'backup_{timestamp}.json'

        self.stdout.write('DB 백업을 시작합니다...')
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                call_command(
                    'dumpdata',
                    '--natural-foreign',
                    '--natural-primary',
                    '--exclude=contenttypes',
                    '--exclude=auth.permission',
                    '--exclude=admin.logentry',
                    '--exclude=sessions.session',
                    '--indent=2',
                    stdout=f,
                )

            size_kb = os.path.getsize(filename) / 1024
            self.stdout.write(self.style.SUCCESS(
                f'백업 완료: {filename.name} ({size_kb:.1f} KB)'
            ))
            logger.info(f'DB backup completed: {filename.name} ({size_kb:.1f} KB)')

            # 오래된 백업 정리
            keep = options['keep']
            backups = sorted(backup_dir.glob('backup_*.json'), reverse=True)
            for old_file in backups[keep:]:
                old_file.unlink()
                self.stdout.write(f'오래된 백업 삭제: {old_file.name}')

        except Exception as e:
            self.stderr.write(self.style.ERROR(f'DB 백업 실패: {e}'))
            logger.error(f'DB backup failed: {e}', exc_info=True)
            if filename.exists():
                filename.unlink()
            raise
