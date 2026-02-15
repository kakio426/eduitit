import json
import sys
import logging
from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '최신 백업 파일의 무결성을 검증합니다.'

    def handle(self, *args, **options):
        backup_dir = settings.BASE_DIR / 'backups'

        if not backup_dir.exists():
            self.stderr.write(self.style.ERROR('백업 디렉토리가 없습니다.'))
            sys.exit(1)

        backups = sorted(backup_dir.glob('backup_*.json'), reverse=True)
        if not backups:
            self.stderr.write(self.style.ERROR('백업 파일이 없습니다.'))
            sys.exit(1)

        latest = backups[0]
        self.stdout.write(f'검증 대상: {latest.name}')

        try:
            with open(latest, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            self.stderr.write(self.style.ERROR(f'JSON 파싱 실패: {e}'))
            sys.exit(1)

        if not isinstance(data, list):
            self.stderr.write(self.style.ERROR('백업 형식이 올바르지 않습니다 (리스트가 아님).'))
            sys.exit(1)

        model_counts = {}
        for obj in data:
            model = obj.get('model', 'unknown')
            model_counts[model] = model_counts.get(model, 0) + 1

        self.stdout.write(f'총 레코드: {len(data)}개')
        self.stdout.write(f'모델 수: {len(model_counts)}개')
        for model, count in sorted(model_counts.items()):
            self.stdout.write(f'  {model}: {count}')

        self.stdout.write(self.style.SUCCESS(
            f'백업 검증 완료: {len(data)}개 레코드, {len(model_counts)}개 모델'
        ))
        logger.info(f'Backup verified: {latest.name} - {len(data)} records, {len(model_counts)} models')
        sys.exit(0)
