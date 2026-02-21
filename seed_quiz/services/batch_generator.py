import calendar
import io
import json
import logging
import os
from dataclasses import dataclass
from datetime import date

from django.utils import timezone

from seed_quiz.models import SQBatchJob, SQQuizBank, SQQuizBankItem
from seed_quiz.services.validator import validate_quiz_payload

logger = logging.getLogger("seed_quiz.batch")

DEFAULT_MODEL = "gpt-4o-mini"
PRESET_LABELS = {
    "general": "상식",
    "math": "수학",
    "korean": "국어",
    "science": "과학",
    "social": "사회",
    "english": "영어",
}


@dataclass
class BatchConfig:
    target_month: date
    preset_types: list[str]
    grades: list[int]
    model: str = DEFAULT_MODEL
    temperature: float = 0.6
    completion_window: str = "24h"


def _month_days(target_month: date) -> list[date]:
    total_days = calendar.monthrange(target_month.year, target_month.month)[1]
    return [date(target_month.year, target_month.month, d) for d in range(1, total_days + 1)]


def _build_prompt(grade: int, preset_type: str, target_date: date) -> str:
    label = PRESET_LABELS.get(preset_type, "상식")
    return (
        f"초등학교 {grade}학년 대상 {label} 퀴즈 3문항을 만들어 주세요. 날짜 컨텍스트는 {target_date.isoformat()}입니다.\n"
        'JSON만 출력: {"items":[{"question_text":"...","choices":["A","B","C","D"],"correct_index":0,"explanation":"...","difficulty":"medium"}]}\n'
        "규칙: 선택지 4개, 정답 인덱스 0~3, 폭력/혐오/정치 선동 금지."
    )


def build_batch_requests(config: BatchConfig) -> list[dict]:
    requests: list[dict] = []
    for target_date in _month_days(config.target_month):
        for preset_type in config.preset_types:
            if preset_type not in PRESET_LABELS:
                continue
            for grade in config.grades:
                if grade not in range(1, 7):
                    continue
                custom_id = f"sq:{target_date.isoformat()}:{preset_type}:{grade}"
                requests.append(
                    {
                        "custom_id": custom_id,
                        "method": "POST",
                        "url": "/v1/chat/completions",
                        "body": {
                            "model": config.model,
                            "messages": [
                                {
                                    "role": "system",
                                    "content": "당신은 초등 교육용 퀴즈 생성기입니다. JSON 이외의 텍스트를 출력하지 마세요.",
                                },
                                {
                                    "role": "user",
                                    "content": _build_prompt(grade, preset_type, target_date),
                                },
                            ],
                            "response_format": {"type": "json_object"},
                            "temperature": config.temperature,
                        },
                    }
                )
    return requests


def _get_openai_client():
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("MASTER_OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY or MASTER_OPENAI_API_KEY not set")
    return OpenAI(api_key=api_key, timeout=30.0)


def submit_batch_job(config: BatchConfig, created_by=None, dry_run: bool = False) -> SQBatchJob:
    requests = build_batch_requests(config)
    job = SQBatchJob.objects.create(
        provider="openai",
        target_month=date(config.target_month.year, config.target_month.month, 1),
        status="pending",
        requested_count=len(requests),
        meta_json={
            "preset_types": config.preset_types,
            "grades": config.grades,
            "model": config.model,
            "completion_window": config.completion_window,
            "dry_run": dry_run,
        },
        created_by=created_by,
    )

    if dry_run:
        logger.info("seed_quiz batch dry-run created job=%s requests=%d", job.id, len(requests))
        return job

    client = _get_openai_client()
    jsonl = "\n".join(json.dumps(item, ensure_ascii=False) for item in requests)
    file_obj = io.BytesIO(jsonl.encode("utf-8"))
    file_obj.name = f"seed_quiz_batch_{config.target_month.isoformat()}.jsonl"

    input_file = client.files.create(file=file_obj, purpose="batch")
    batch = client.batches.create(
        input_file_id=input_file.id,
        endpoint="/v1/chat/completions",
        completion_window=config.completion_window,
        metadata={
            "kind": "seed_quiz_monthly",
            "target_month": config.target_month.isoformat(),
        },
    )

    job.batch_id = batch.id
    job.input_file_id = input_file.id
    job.status = "submitted"
    job.save(update_fields=["batch_id", "input_file_id", "status", "updated_at"])
    logger.info("seed_quiz batch submitted job=%s batch_id=%s", job.id, job.batch_id)
    return job


def _map_openai_batch_status(status: str) -> str:
    allowed = {choice for choice, _ in SQBatchJob.STATUS_CHOICES}
    if status in allowed:
        return status
    if status == "cancelling":
        return "cancelled"
    return "failed"


def sync_batch_job_status(job: SQBatchJob) -> SQBatchJob:
    if not job.batch_id:
        return job
    client = _get_openai_client()
    batch = client.batches.retrieve(job.batch_id)

    new_status = _map_openai_batch_status(getattr(batch, "status", "failed"))
    job.status = new_status
    job.output_file_id = getattr(batch, "output_file_id", "") or ""
    job.error_file_id = getattr(batch, "error_file_id", "") or ""
    if new_status in {"completed", "failed", "cancelled"} and not job.completed_at:
        job.completed_at = timezone.now()
    job.save(update_fields=["status", "output_file_id", "error_file_id", "completed_at", "updated_at"])
    return job


def _extract_payload_from_line(line_obj: dict) -> dict | None:
    response = line_obj.get("response") or {}
    body = response.get("body") or {}
    choices = body.get("choices") or []
    if not choices:
        return None
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not content:
        return None
    try:
        return json.loads(content)
    except Exception:
        return None


def _parse_custom_id(custom_id: str) -> tuple[date, str, int] | None:
    # sq:2026-03-01:general:3
    parts = (custom_id or "").split(":")
    if len(parts) != 4 or parts[0] != "sq":
        return None
    try:
        target_date = date.fromisoformat(parts[1])
        preset_type = parts[2]
        grade = int(parts[3])
    except Exception:
        return None
    if preset_type not in PRESET_LABELS or grade not in range(1, 7):
        return None
    return target_date, preset_type, grade


def ingest_completed_batch_output(job: SQBatchJob) -> SQBatchJob:
    if job.status != "completed" or not job.output_file_id:
        return job
    if job.meta_json.get("ingested"):
        return job

    client = _get_openai_client()
    content_resp = client.files.content(job.output_file_id)
    if hasattr(content_resp, "text"):
        raw_text = content_resp.text
    elif hasattr(content_resp, "read"):
        raw = content_resp.read()
        raw_text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
    else:
        raw_text = str(content_resp)

    success = 0
    failed = 0
    for line in (raw_text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            line_obj = json.loads(line)
        except Exception:
            failed += 1
            continue

        parsed_meta = _parse_custom_id(line_obj.get("custom_id", ""))
        payload = _extract_payload_from_line(line_obj)
        if not parsed_meta or not payload:
            failed += 1
            continue
        target_date, preset_type, grade = parsed_meta

        ok, errors = validate_quiz_payload(payload)
        if not ok:
            logger.warning("seed_quiz batch payload invalid custom_id=%s errors=%s", line_obj.get("custom_id"), errors)
            failed += 1
            continue

        title = f"[공식] {target_date.isoformat()} {grade}학년 {PRESET_LABELS[preset_type]}"
        bank, _ = SQQuizBank.objects.get_or_create(
            title=title,
            preset_type=preset_type,
            grade=grade,
            source="ai",
            is_official=True,
            defaults={
                "is_public": False,
                "share_opt_in": False,
                "quality_status": "approved",
                "is_active": True,
                "available_from": target_date,
                "available_to": target_date,
            },
        )
        bank.is_official = True
        bank.is_public = False
        bank.share_opt_in = False
        bank.quality_status = "approved"
        bank.is_active = True
        bank.available_from = target_date
        bank.available_to = target_date
        bank.save(
            update_fields=[
                "is_official",
                "is_public",
                "share_opt_in",
                "quality_status",
                "is_active",
                "available_from",
                "available_to",
                "updated_at",
            ]
        )
        bank.items.all().delete()
        for order_no, item in enumerate(payload["items"], start=1):
            SQQuizBankItem.objects.create(
                bank=bank,
                order_no=order_no,
                question_text=item["question_text"],
                choices=item["choices"],
                correct_index=item["correct_index"],
                explanation=item.get("explanation", ""),
                difficulty=item.get("difficulty", "medium"),
            )
        success += 1

    meta = dict(job.meta_json or {})
    meta["ingested"] = True
    meta["ingested_at"] = timezone.now().isoformat()
    job.meta_json = meta
    job.success_count = success
    job.failed_count = failed
    job.save(update_fields=["meta_json", "success_count", "failed_count", "updated_at"])
    logger.info("seed_quiz batch ingested job=%s success=%d failed=%d", job.id, success, failed)
    return job
