from django.core.management import call_command, get_commands
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    FILE_RETENTION_DAYS = 365
    REQUEST_RETENTION_DAYS = 365

    help = (
        '수합 자동 정리: 문서 파일과 요청 데이터를 1년 기준으로 삭제'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='실제 삭제 없이 대상만 확인',
        )
        parser.add_argument(
            '--skip-consent',
            action='store_true',
            help='동의서 정리(cleanup_consent) 연동 실행 생략',
        )

    def handle(self, *args, **options):
        from collect.models import CollectionRequest, Submission
        dry_run = options['dry_run']
        now = timezone.now()

        self.stdout.write('=' * 70)
        self.stdout.write('[Collect Cleanup]')
        if dry_run:
            self.stdout.write('[DRY RUN] 실제 삭제 없이 대상만 표시합니다.')
        self.stdout.write('=' * 70)

        # 1단계: 마감(closed) 후 1년 경과 → 파일 삭제 + archived 전환
        closed_requests = CollectionRequest.objects.filter(status='closed')

        archived_count = 0
        files_deleted = 0
        for req in closed_requests:
            # closed_at이 없던 기존 데이터는 updated_at을 fallback으로 사용
            closed_base = req.closed_at or req.updated_at
            file_cleanup_due_at = closed_base + timedelta(days=self.FILE_RETENTION_DAYS)
            if req.retention_until and req.retention_until > file_cleanup_due_at:
                file_cleanup_due_at = req.retention_until
            if file_cleanup_due_at > now:
                continue

            file_submissions = Submission.objects.filter(
                collection_request=req,
                submission_type='file',
            ).exclude(file='')

            for sub in file_submissions:
                if sub.file:
                    self.stdout.write(f'  [파일 삭제] {sub.original_filename} (요청: {req.title})')
                    if not dry_run:
                        try:
                            sub.file.delete(save=False)
                            sub.file = None
                            sub.save()
                            files_deleted += 1
                        except Exception as e:
                            logger.error(f'파일 삭제 실패: {sub.original_filename} - {e}')

            # 양식 파일도 삭제
            if req.template_file:
                self.stdout.write(f'  [양식 삭제] {req.template_file_name} (요청: {req.title})')
                if not dry_run:
                    try:
                        req.template_file.delete(save=False)
                        req.template_file = None
                        req.template_file_name = ''
                    except Exception as e:
                        logger.error(f'양식 파일 삭제 실패: {req.template_file_name} - {e}')

            if not dry_run:
                req.status = 'archived'
                req.save(update_fields=["status", "updated_at"])
            archived_count += 1
            self.stdout.write(f'  [보관 전환] {req.title}')

        self.stdout.write(
            f"\n[1단계] 마감 후 {self.FILE_RETENTION_DAYS}일 경과: "
            f"{archived_count}개 보관 전환, {files_deleted}개 파일 삭제"
        )

        # 2단계: 생성 후 1년 경과 → 요청 자체 삭제

        all_requests = CollectionRequest.objects.all()
        delete_targets = []

        for req in all_requests:
            request_cleanup_due_at = req.created_at + timedelta(days=self.REQUEST_RETENTION_DAYS)

            if req.retention_until and req.retention_until > request_cleanup_due_at:
                request_cleanup_due_at = req.retention_until

            if request_cleanup_due_at <= now:
                delete_targets.append(req)

        old_count = len(delete_targets)
        if old_count > 0:
            for req in delete_targets:
                self.stdout.write(
                    f'  [요청 삭제] {req.title} '
                    f'(생성: {req.created_at.strftime("%Y-%m-%d")}, {self.REQUEST_RETENTION_DAYS}일 경과)'
                )
                # 남아있는 파일 정리
                if not dry_run:
                    try:
                        for sub in req.submissions.filter(submission_type='file').exclude(file=''):
                            if sub.file:
                                try:
                                    sub.file.delete(save=False)
                                except Exception as e:
                                    logger.error(f'파일 삭제 실패: {e}')
                        if req.template_file:
                            try:
                                req.template_file.delete(save=False)
                            except Exception as e:
                                logger.error(f'양식 파일 삭제 실패: {e}')
                    except Exception as e:
                        logger.error(f'요청 삭제 사전정리 실패 (id={req.id}, title={req.title}): {e}')
                    try:
                        req.delete()
                    except Exception as e:
                        logger.error(f'요청 삭제 실패 (id={req.id}, title={req.title}): {e}')
                        continue

        self.stdout.write(
            f"[2단계] 만료 요청: {old_count}개 삭제 (생성 후 {self.REQUEST_RETENTION_DAYS}일)"
        )
        self.stdout.write('=' * 70)
        self.stdout.write('[OK] Done!')

        if options.get('skip_consent'):
            self.stdout.write('[연동 생략] cleanup_consent (--skip-consent)')
            return

        if 'cleanup_consent' not in get_commands():
            self.stdout.write(self.style.WARNING('[연동 생략] cleanup_consent 명령을 찾을 수 없습니다.'))
            return

        self.stdout.write('=' * 70)
        self.stdout.write('[연동 실행] cleanup_consent')
        call_command('cleanup_consent', dry_run=dry_run)
