import re

from django.core.management.base import BaseCommand
from django.db import transaction

from signatures.models import AffiliationCorrectionLog, ExpectedParticipant, Signature


def normalize_affiliation_text(value):
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    normalized = normalized.replace("—", "-").replace("–", "-")
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"\s*/\s*", "/", normalized)
    normalized = re.sub(r"\s*-\s*", "-", normalized)
    return normalized[:100]


class Command(BaseCommand):
    help = "기존 직위/학년반 데이터를 정규화합니다. 기본은 미리보기이며 --apply로 반영합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="실제로 DB 값을 수정합니다. 생략 시 미리보기만 출력합니다.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="처리할 최대 건수(0은 전체).",
        )
        parser.add_argument(
            "--session-id",
            type=int,
            default=0,
            help="특정 연수 ID만 정규화합니다.",
        )

    def handle(self, *args, **options):
        apply_changes = bool(options.get("apply"))
        limit = max(0, int(options.get("limit") or 0))
        session_id = int(options.get("session_id") or 0)

        signature_qs = Signature.objects.select_related("training_session").all().order_by("id")
        participant_qs = ExpectedParticipant.objects.select_related("training_session").all().order_by("id")

        if session_id > 0:
            signature_qs = signature_qs.filter(training_session_id=session_id)
            participant_qs = participant_qs.filter(training_session_id=session_id)

        total_candidates = 0
        updated_signatures = 0
        updated_participants = 0
        preview_rows = []
        reason = "기존 데이터 공백/구분자 정규화 스크립트"

        if apply_changes:
            self.stdout.write(self.style.WARNING("정규화를 실제 반영합니다 (--apply)."))
        else:
            self.stdout.write(self.style.WARNING("미리보기 모드입니다. (--apply 없음)"))

        with transaction.atomic():
            for signature in signature_qs:
                updates = {}
                old_raw = signature.participant_affiliation or ""
                old_corrected = signature.corrected_affiliation or ""
                normalized_raw = normalize_affiliation_text(old_raw)
                normalized_corrected = normalize_affiliation_text(old_corrected)
                before_display = signature.display_affiliation

                if old_corrected.strip():
                    if normalized_corrected != old_corrected:
                        updates["corrected_affiliation"] = normalized_corrected
                elif normalized_raw != old_raw:
                    updates["participant_affiliation"] = normalized_raw

                if not updates:
                    continue

                total_candidates += 1
                after_raw = updates.get("participant_affiliation", old_raw)
                after_corrected = updates.get("corrected_affiliation", old_corrected)
                after_display = (after_corrected or after_raw or "").strip()

                if len(preview_rows) < 10:
                    preview_rows.append(
                        f"[Signature #{signature.id}] {before_display or '-'} -> {after_display or '-'}"
                    )

                if not apply_changes:
                    if limit and total_candidates >= limit:
                        break
                    continue

                for field, value in updates.items():
                    setattr(signature, field, value)
                signature.save(update_fields=list(updates.keys()))
                updated_signatures += 1

                AffiliationCorrectionLog.objects.create(
                    training_session=signature.training_session,
                    target_type=AffiliationCorrectionLog.TARGET_SIGNATURE,
                    mode=AffiliationCorrectionLog.MODE_SCRIPT,
                    signature=signature,
                    before_affiliation=normalize_affiliation_text(before_display),
                    after_affiliation=normalize_affiliation_text(after_display),
                    reason=reason,
                )
                if limit and total_candidates >= limit:
                    break

            if not (limit and total_candidates >= limit):
                for participant in participant_qs:
                    updates = {}
                    old_raw = participant.affiliation or ""
                    old_corrected = participant.corrected_affiliation or ""
                    normalized_raw = normalize_affiliation_text(old_raw)
                    normalized_corrected = normalize_affiliation_text(old_corrected)
                    before_display = participant.display_affiliation

                    if old_corrected.strip():
                        if normalized_corrected != old_corrected:
                            updates["corrected_affiliation"] = normalized_corrected
                    elif normalized_raw != old_raw:
                        updates["affiliation"] = normalized_raw

                    if not updates:
                        continue

                    total_candidates += 1
                    after_raw = updates.get("affiliation", old_raw)
                    after_corrected = updates.get("corrected_affiliation", old_corrected)
                    after_display = (after_corrected or after_raw or "").strip()

                    if len(preview_rows) < 10:
                        preview_rows.append(
                            f"[Participant #{participant.id}] {before_display or '-'} -> {after_display or '-'}"
                        )

                    if not apply_changes:
                        if limit and total_candidates >= limit:
                            break
                        continue

                    for field, value in updates.items():
                        setattr(participant, field, value)
                    participant.save(update_fields=list(updates.keys()))
                    updated_participants += 1

                    AffiliationCorrectionLog.objects.create(
                        training_session=participant.training_session,
                        target_type=AffiliationCorrectionLog.TARGET_PARTICIPANT,
                        mode=AffiliationCorrectionLog.MODE_SCRIPT,
                        expected_participant=participant,
                        before_affiliation=normalize_affiliation_text(before_display),
                        after_affiliation=normalize_affiliation_text(after_display),
                        reason=reason,
                    )
                    if limit and total_candidates >= limit:
                        break

            if not apply_changes:
                transaction.set_rollback(True)

        if preview_rows:
            self.stdout.write("변경 예시:")
            for row in preview_rows:
                self.stdout.write(f" - {row}")
        else:
            self.stdout.write("정규화가 필요한 데이터가 없습니다.")

        if apply_changes:
            self.stdout.write(
                self.style.SUCCESS(
                    f"완료: 총 {total_candidates}건 반영 (서명 {updated_signatures}건, 명단 {updated_participants}건)"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"미리보기: 총 {total_candidates}건 변경 대상 (서명/명단 합산). 반영하려면 --apply를 사용하세요."
                )
            )
