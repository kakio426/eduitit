from datetime import timedelta
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    DOCUMENT_RETENTION_DAYS = 365
    help = "동의서 자동 정리: 문서 관련 파일을 1년 기준으로 삭제"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="실제 삭제 없이 대상만 확인",
        )

    def handle(self, *args, **options):
        from consent.models import SignatureDocument, SignatureRecipient, SignatureRequest

        dry_run = options["dry_run"]
        now = timezone.now()
        document_cutoff = now - timedelta(days=self.DOCUMENT_RETENTION_DAYS)

        merged_deleted = 0
        signed_deleted = 0
        original_deleted = 0

        self.stdout.write("=" * 70)
        self.stdout.write("[Consent Cleanup]")
        if dry_run:
            self.stdout.write("[DRY RUN] 실제 삭제 없이 대상만 표시합니다.")
        self.stdout.write("=" * 70)

        requests_with_merged = SignatureRequest.objects.exclude(merged_pdf="")
        for request_item in requests_with_merged:
            if request_item.created_at > document_cutoff:
                continue
            if (
                request_item.status == SignatureRequest.STATUS_SENT
                and not request_item.is_link_expired
            ):
                continue

            self.stdout.write(
                f"  [merged_pdf 삭제] {request_item.title} "
                f"(생성: {request_item.created_at.strftime('%Y-%m-%d')})"
            )
            if not dry_run:
                try:
                    request_item.merged_pdf.delete(save=False)
                    request_item.merged_pdf = None
                    request_item.save(update_fields=["merged_pdf"])
                    merged_deleted += 1
                except Exception as exc:
                    logger.error("consent merged_pdf 삭제 실패 id=%s err=%s", request_item.id, exc)

        recipients_with_signed = SignatureRecipient.objects.exclude(signed_pdf="")
        for recipient in recipients_with_signed:
            base_time = recipient.signed_at or recipient.created_at
            if base_time > document_cutoff:
                continue

            self.stdout.write(
                f"  [signed_pdf 삭제] {recipient.student_name}/{recipient.parent_name} "
                f"(기준일: {base_time.strftime('%Y-%m-%d')})"
            )
            if not dry_run:
                try:
                    recipient.signed_pdf.delete(save=False)
                    recipient.signed_pdf = None
                    recipient.save(update_fields=["signed_pdf"])
                    signed_deleted += 1
                except Exception as exc:
                    logger.error("consent signed_pdf 삭제 실패 id=%s err=%s", recipient.id, exc)

        documents_with_original = SignatureDocument.objects.exclude(original_file="")
        for document in documents_with_original:
            if document.created_at > document_cutoff:
                continue
            recent_or_active_exists = SignatureRequest.objects.filter(document=document).filter(
                created_at__gt=document_cutoff
            ).exists()
            if recent_or_active_exists:
                continue

            self.stdout.write(
                f"  [original_file 삭제] {document.title} "
                f"(생성: {document.created_at.strftime('%Y-%m-%d')})"
            )
            if not dry_run:
                try:
                    document.original_file.delete(save=False)
                    document.original_file = ""
                    document.save(update_fields=["original_file"])
                    original_deleted += 1
                except Exception as exc:
                    logger.error("consent original_file 삭제 실패 id=%s err=%s", document.id, exc)

        self.stdout.write(
            f"[정리 결과] merged_pdf={merged_deleted}, signed_pdf={signed_deleted}, original_file={original_deleted}"
        )
        self.stdout.write("=" * 70)
        self.stdout.write("[OK] Done!")
