from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        '수합 자동 정리: 마감 후 27일 파일 삭제/보관 전환 + '
        '첫 제출 후 50일(미제출 시 생성 후 80일) 요청 삭제'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='실제 삭제 없이 대상만 확인',
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

        # 1단계: 마감(closed) 후 27일 경과 → 파일 삭제 + archived 전환
        closed_requests = CollectionRequest.objects.filter(status='closed')

        archived_count = 0
        files_deleted = 0
        for req in closed_requests:
            # closed_at이 없던 기존 데이터는 updated_at을 fallback으로 사용
            closed_base = req.closed_at or req.updated_at
            file_cleanup_due_at = closed_base + timedelta(days=27)
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

        self.stdout.write(f'\n[1단계] 마감 후 27일 경과: {archived_count}개 보관 전환, {files_deleted}개 파일 삭제')

        # 2단계: 첫 제출 후 50일 경과 또는 제출 없이 생성 후 80일 경과 → 요청 자체 삭제

        all_requests = CollectionRequest.objects.all()
        delete_targets = []

        for req in all_requests:
            first_submission = req.submissions.order_by('submitted_at').first()
            if first_submission:
                request_cleanup_due_at = first_submission.submitted_at + timedelta(days=50)
            else:
                request_cleanup_due_at = req.created_at + timedelta(days=80)

            if req.retention_until and req.retention_until > request_cleanup_due_at:
                request_cleanup_due_at = req.retention_until

            if request_cleanup_due_at <= now:
                delete_targets.append(req)

        old_count = len(delete_targets)
        if old_count > 0:
            for req in delete_targets:
                first_sub = req.submissions.order_by('submitted_at').first()
                if first_sub:
                    self.stdout.write(f'  [요청 삭제] {req.title} (첫 제출: {first_sub.submitted_at.strftime("%Y-%m-%d")})')
                else:
                    self.stdout.write(f'  [요청 삭제] {req.title} (생성: {req.created_at.strftime("%Y-%m-%d")}, 제출 없음)')
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

        self.stdout.write(f'[2단계] 만료 요청: {old_count}개 삭제 (첫 제출+50일 / 미제출+80일)')
        self.stdout.write('=' * 70)
        self.stdout.write('[OK] Done!')
