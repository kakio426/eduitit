"""
관리자/교사용 퀴즈 은행 서비스.
"""

import csv
import io
import logging
import json
import os
import hashlib

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from seed_quiz.models import SQGenerationLog, SQQuizBank, SQQuizBankItem, SQQuizItem, SQQuizSet
from seed_quiz.topics import DEFAULT_TOPIC, TOPIC_LABELS, normalize_topic
from seed_quiz.services.validator import normalize_and_check, validate_quiz_payload

logger = logging.getLogger("seed_quiz.bank")

VALID_PRESET_TYPES = set(TOPIC_LABELS.keys())
VALID_DIFFICULTIES = {"easy", "medium", "hard"}

CSV_HEADER_ALIASES = {
    # Legacy compatibility: old templates may still include set_title.
    "set_title": ["set_title", "묶음이름", "세트코드", "세트명", "세트코드(set_title)"],
    "preset_type": ["preset_type", "주제"],
    "grade": ["grade", "학년"],
    "question_text": ["question_text", "문제", "문항"],
    "choice_1": ["choice_1", "보기1", "보기 1"],
    "choice_2": ["choice_2", "보기2", "보기 2"],
    "choice_3": ["choice_3", "보기3", "보기 3"],
    "choice_4": ["choice_4", "보기4", "보기 4"],
    "correct_index": ["correct_index", "정답번호", "정답인덱스", "정답"],
    "explanation": ["explanation", "해설"],
    "difficulty": ["difficulty", "난이도"],
}
CSV_HEADER_ALIAS_MAP = {
    alias.strip().lower(): canonical
    for canonical, aliases in CSV_HEADER_ALIASES.items()
    for alias in aliases
}
DIFFICULTY_ALIASES = {
    "easy": "easy",
    "쉬움": "easy",
    "medium": "medium",
    "보통": "medium",
    "중간": "medium",
    "hard": "hard",
    "어려움": "hard",
}
CSV_HEADER_DISPLAY = {
    "set_title": "내부세트이름",
    "preset_type": "주제",
    "grade": "학년",
    "question_text": "문제",
    "choice_1": "보기1",
    "choice_2": "보기2",
    "choice_3": "보기3",
    "choice_4": "보기4",
    "correct_index": "정답번호",
    "explanation": "해설",
    "difficulty": "난이도",
}


def _is_guide_row(row: dict) -> bool:
    """CSV 템플릿 안내행(주석/가이드)을 업로드 시 무시한다."""
    if not row:
        return False
    ordered_keys = [
        "preset_type",
        "grade",
        "question_text",
        "choice_1",
        "choice_2",
        "choice_3",
        "choice_4",
        "correct_index",
        "explanation",
        "difficulty",
        "set_title",
    ]
    first_non_empty = ""
    for key in ordered_keys:
        value = str(row.get(key) or "").strip()
        if value:
            first_non_empty = value
            break
    if not first_non_empty:
        for value in row.values():
            raw = str(value or "").strip()
            if raw:
                first_non_empty = raw
                break
    return first_non_empty.startswith("#") or first_non_empty.startswith("※")


def _normalize_source_text(source_text: str) -> str:
    # 연속 공백을 하나로 압축해 의미가 같은 입력은 같은 해시로 취급한다.
    return " ".join((source_text or "").split())


def _source_hash(source_text: str) -> str:
    return hashlib.sha256(source_text.encode("utf-8")).hexdigest()


def copy_bank_to_draft(bank_id, classroom, teacher) -> SQQuizSet:
    """
    은행 세트를 교실용 draft SQQuizSet으로 복사한다.
    같은 날짜/과목 draft가 있으면 문항을 교체해 재사용한다.
    """
    bank = SQQuizBank.objects.prefetch_related("items").get(id=bank_id, is_active=True)
    bank_items = list(bank.items.order_by("order_no"))
    if not bank_items:
        raise ValueError("퀴즈 은행 세트에 문항이 없습니다.")
    target_date = timezone.localdate()

    with transaction.atomic():
        quiz_set, created = SQQuizSet.objects.get_or_create(
            classroom=classroom,
            target_date=target_date,
            preset_type=bank.preset_type,
            status="draft",
            defaults={
                "grade": bank.grade,
                "title": bank.title,
                "source": "bank",
                "bank_source": bank,
                "created_by": teacher,
            },
        )
        if not created:
            quiz_set.items.all().delete()
            quiz_set.title = bank.title
            quiz_set.grade = bank.grade
            quiz_set.source = "bank"
            quiz_set.bank_source = bank
            quiz_set.save(update_fields=["title", "grade", "source", "bank_source"])

        for bank_item in bank_items:
            SQQuizItem.objects.create(
                quiz_set=quiz_set,
                order_no=bank_item.order_no,
                question_text=bank_item.question_text,
                choices=bank_item.choices,
                correct_index=bank_item.correct_index,
                explanation=bank_item.explanation,
                difficulty=bank_item.difficulty,
            )

    SQQuizBank.objects.filter(id=bank.id).update(use_count=F("use_count") + 1)
    logger.info(
        "seed_quiz bank copied bank=%s quiz_set=%s classroom=%s",
        str(bank.id),
        str(quiz_set.id),
        str(classroom.id),
    )
    return quiz_set


def _decode_csv_text(csv_file_or_bytes) -> str:
    raw = csv_file_or_bytes.read() if hasattr(csv_file_or_bytes, "read") else csv_file_or_bytes
    if isinstance(raw, bytes):
        try:
            return raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            return raw.decode("cp949")
    return raw


def _canonical_header(name: str) -> str:
    key = str(name or "").strip().lower()
    if not key:
        return ""
    return CSV_HEADER_ALIAS_MAP.get(key, key)


def _canonicalize_row(raw_row: dict) -> dict:
    normalized: dict = {}
    for raw_key, value in (raw_row or {}).items():
        canonical = _canonical_header(raw_key)
        if not canonical:
            continue
        if canonical not in normalized or not str(normalized[canonical] or "").strip():
            normalized[canonical] = value
    return normalized


def _parse_grade_value(raw_grade: str) -> tuple[int | None, str | None]:
    grade_text = (raw_grade or "3").strip()
    if grade_text in ("학년무관", "0"):
        return 0, None
    try:
        grade_value = int(grade_text)
    except ValueError:
        return None, "학년이 올바르지 않습니다 (1~6 또는 학년무관)."
    if grade_value not in range(1, 7):
        return None, "학년은 1~6 또는 학년무관이어야 합니다."
    return grade_value, None


def _build_auto_set_title(preset_type: str, grade: int, items_data: list[dict]) -> str:
    grade_token = "ANY" if grade == 0 else f"G{grade}"
    signature_payload = {
        "preset_type": preset_type,
        "grade": grade,
        "items": [
            {
                "question_text": item.get("question_text", ""),
                "choices": item.get("choices", []),
                "correct_index": item.get("correct_index", 0),
                "explanation": item.get("explanation", ""),
                "difficulty": item.get("difficulty", "medium"),
            }
            for item in items_data
        ],
    }
    digest = hashlib.sha1(
        json.dumps(signature_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    return f"CSV-{preset_type}-{grade_token}-{digest}"


def parse_csv_upload(
    csv_file_or_bytes,
    max_rows: int | None = None,
    max_sets: int | None = None,
) -> tuple[list[dict], list[str]]:
    """
    CSV를 파싱/검증해 미리보기 가능한 구조로 반환한다.
    반환: (parsed_sets, errors)
    """
    errors: list[str] = []
    parsed_sets: list[dict] = []

    try:
        text = _decode_csv_text(csv_file_or_bytes)
    except Exception as e:
        return [], [f"파일 읽기 실패: {e}"]

    reader = csv.DictReader(io.StringIO(text))
    required_cols = {
        "preset_type",
        "grade",
        "question_text",
        "choice_1",
        "choice_2",
        "choice_3",
        "choice_4",
        "correct_index",
    }
    if not reader.fieldnames:
        return [], ["CSV 헤더가 없습니다."]

    canonical_fieldnames = {_canonical_header(name) for name in reader.fieldnames}
    missing_cols = required_cols - canonical_fieldnames
    if missing_cols:
        missing_labels = [CSV_HEADER_DISPLAY.get(col, col) for col in sorted(missing_cols)]
        return [], [f"필수 컬럼 누락: {', '.join(missing_labels)}"]

    data_rows: list[tuple[int, dict]] = []
    data_row_count = 0
    for row_no, raw_row in enumerate(reader, start=2):
        row = _canonicalize_row(raw_row)
        if _is_guide_row(row):
            continue
        if not any(str(v or "").strip() for v in row.values()):
            continue
        data_row_count += 1
        if max_rows and data_row_count > max_rows:
            return [], [
                f"CSV 행 수가 제한({max_rows}행)을 초과했습니다. "
                "파일을 분할해 다시 업로드해 주세요."
            ]
        data_rows.append((row_no, row))

    if not data_rows:
        return [], []

    # 묶음이름 없는 단순 모드: 파일 전체를 1세트로 처리한다.
    set_count = 1
    if max_sets and set_count > max_sets:
        return [], [
            f"CSV 세트 수가 제한({max_sets}세트)을 초과했습니다. "
            "파일을 분할해 다시 업로드해 주세요."
        ]

    first_row_no, first = data_rows[0]
    last_row_no = data_rows[-1][0]
    set_label = f"업로드 세트(행 {first_row_no}~{last_row_no})"
    preset_raw = (first.get("preset_type") or "").strip()
    preset_type = normalize_topic(preset_raw)
    if not preset_type:
        return [], [f"{set_label}: 잘못된 주제 '{preset_raw}'."]

    grade, grade_error = _parse_grade_value(first.get("grade") or "3")
    if grade_error:
        return [], [f"{set_label}: {grade_error}"]

    items_data = []
    for row_no, row in data_rows:
        raw_preset = (row.get("preset_type") or "").strip()
        row_preset = normalize_topic(raw_preset)
        if not row_preset:
            errors.append(f"행 {row_no}: 잘못된 주제 '{raw_preset}'.")
            break
        if row_preset != preset_type:
            errors.append(f"{set_label}: 주제는 모든 문항에서 동일해야 합니다.")
            break

        row_grade, row_grade_error = _parse_grade_value(row.get("grade") or "3")
        if row_grade_error:
            errors.append(f"행 {row_no}: {row_grade_error}")
            break
        if row_grade != grade:
            errors.append(f"{set_label}: 학년은 모든 문항에서 동일해야 합니다.")
            break

        question_text = (row.get("question_text") or "").strip()
        if not question_text:
            errors.append(f"행 {row_no}: question_text가 비어있습니다.")
            break

        try:
            question_text = normalize_and_check(question_text)
            choices = [
                normalize_and_check((row.get("choice_1") or "").strip()),
                normalize_and_check((row.get("choice_2") or "").strip()),
                normalize_and_check((row.get("choice_3") or "").strip()),
                normalize_and_check((row.get("choice_4") or "").strip()),
            ]
        except ValueError:
            errors.append(f"행 {row_no}: 텍스트에 허용되지 않는 문자가 포함되어 있습니다.")
            break

        if any(not c for c in choices):
            errors.append(f"행 {row_no}: 선택지에 빈 항목이 있습니다.")
            break
        if len(set(choices)) != 4:
            errors.append(f"행 {row_no}: 선택지에 중복이 있습니다.")
            break

        try:
            correct_index_raw = int((row.get("correct_index") or "1").strip())
        except ValueError:
            errors.append(f"행 {row_no}: 정답번호가 정수가 아닙니다.")
            break
        if correct_index_raw not in range(1, 5):
            errors.append(f"행 {row_no}: 정답번호는 1~4이어야 합니다 (보기1=1, 보기2=2, 보기3=3, 보기4=4).")
            break
        correct_index = correct_index_raw - 1  # 1-기반 입력 -> 0-기반 저장

        explanation_raw = (row.get("explanation") or "").strip()
        try:
            explanation = normalize_and_check(explanation_raw) if explanation_raw else ""
        except ValueError:
            errors.append(f"행 {row_no}: 해설에 허용되지 않는 문자가 포함되어 있습니다.")
            break

        difficulty_raw = (row.get("difficulty") or "medium").strip() or "medium"
        difficulty = (
            DIFFICULTY_ALIASES.get(difficulty_raw.lower())
            or DIFFICULTY_ALIASES.get(difficulty_raw)
            or "medium"
        )
        if difficulty not in VALID_DIFFICULTIES:
            difficulty = "medium"

        items_data.append(
            {
                "question_text": question_text,
                "choices": choices,
                "correct_index": correct_index,
                "explanation": explanation,
                "difficulty": difficulty,
            }
        )

    if errors:
        return [], errors

    payload = {"items": items_data}
    ok, validate_errors = validate_quiz_payload(payload)
    if not ok:
        return [], [f"{set_label}: 규칙 검증 실패({', '.join(validate_errors)})."]

    set_title = _build_auto_set_title(preset_type, grade, items_data)
    parsed_sets.append(
        {
            "set_title": set_title,
            "preset_type": preset_type,
            "preset_label": TOPIC_LABELS.get(preset_type, preset_type),
            "grade": grade,
            "items": items_data,
        }
    )

    return parsed_sets, errors


def save_parsed_sets_to_bank(parsed_sets: list[dict], created_by, share_opt_in: bool = False) -> tuple[int, int, int]:
    """
    parse 완료 데이터를 SQQuizBank에 저장한다.
    반환: (created_count, updated_count, review_count)
    """
    created_count = 0
    updated_count = 0
    review_count = 0

    quality_status = "review" if share_opt_in else "approved"
    is_public = False

    for parsed in parsed_sets:
        set_title = parsed["set_title"]
        preset_type = parsed["preset_type"]
        grade = parsed["grade"]
        items_data = parsed["items"]

        with transaction.atomic():
            bank, created = SQQuizBank.objects.get_or_create(
                title=set_title,
                preset_type=preset_type,
                grade=grade,
                source="csv",
                created_by=created_by,
                defaults={
                    "is_active": True,
                    "is_public": is_public,
                    "is_official": False,
                    "share_opt_in": share_opt_in,
                    "quality_status": quality_status,
                },
            )
            if created:
                created_count += 1
            else:
                bank.items.all().delete()
                bank.is_active = True
                bank.is_official = False
                bank.is_public = is_public
                bank.share_opt_in = share_opt_in
                bank.quality_status = quality_status
                bank.reviewed_by = None
                bank.reviewed_at = None
                bank.save(
                    update_fields=[
                        "is_active",
                        "is_official",
                        "is_public",
                        "share_opt_in",
                        "quality_status",
                        "reviewed_by",
                        "reviewed_at",
                    ]
                )
                updated_count += 1

            for order_no, item_data in enumerate(items_data, start=1):
                SQQuizBankItem.objects.create(bank=bank, order_no=order_no, **item_data)

            SQGenerationLog.objects.create(
                level="info",
                code="BANK_CSV_IMPORTED",
                message=f"CSV 임포트: {set_title}",
                payload={
                    "bank_id": str(bank.id),
                    "created": created,
                    "share_opt_in": share_opt_in,
                    "quality_status": quality_status,
                },
            )

            if quality_status == "review":
                review_count += 1

    return created_count, updated_count, review_count


def import_csv_to_bank(csv_file, created_by) -> tuple[int, list[str]]:
    """
    호환용 래퍼: CSV를 즉시 저장한다(공유 신청 없음).
    """
    parsed_sets, errors = parse_csv_upload(csv_file)
    if errors:
        return 0, errors
    created_count, _, _ = save_parsed_sets_to_bank(
        parsed_sets=parsed_sets,
        created_by=created_by,
        share_opt_in=False,
    )
    return created_count, []


def generate_bank_from_ai(preset_type: str, grade: int, created_by) -> SQQuizBank:
    """
    AI 호출 -> 검증 -> SQQuizBank 저장.
    """
    from seed_quiz.services.generation import _call_ai

    preset_type = normalize_topic(preset_type) or DEFAULT_TOPIC
    payload = _call_ai(grade, preset_type)
    ok, errors = validate_quiz_payload(payload)
    if not ok:
        raise ValueError(f"AI 생성 검증 실패: {errors}")

    title_date = timezone.localdate().isoformat()
    label = TOPIC_LABELS.get(preset_type, "주제")
    title = f"[AI] {grade}학년 {label} {title_date}"

    with transaction.atomic():
        bank = SQQuizBank.objects.create(
            preset_type=preset_type,
            grade=grade,
            title=title,
            source="ai",
            is_official=False,
            is_public=False,
            share_opt_in=False,
            quality_status="approved",
            is_active=True,
            created_by=created_by,
        )
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

    SQGenerationLog.objects.create(
        level="info",
        code="BANK_AI_CREATED",
        message=f"AI 은행 생성: {title}",
        payload={"bank_id": str(bank.id), "preset_type": preset_type, "grade": grade},
    )
    return bank


def generate_bank_from_context_ai(preset_type: str, grade: int, source_text: str, created_by) -> tuple[SQQuizBank, bool]:
    """
    입력 지문(source_text)을 근거로 퀴즈 은행 세트를 생성한다.
    반환: (bank, cached)
    """
    from openai import OpenAI

    preset_type = normalize_topic(preset_type) or DEFAULT_TOPIC
    normalized_source_text = _normalize_source_text(source_text)
    if len(normalized_source_text) < 20:
        raise ValueError("지문이 너무 짧습니다. 20자 이상 입력해 주세요.")
    if len(normalized_source_text) > 4000:
        raise ValueError("지문이 너무 깁니다. 4000자 이하로 입력해 주세요.")

    source_hash = _source_hash(normalized_source_text)
    cached_bank = (
        SQQuizBank.objects.filter(
            source_hash=source_hash,
            preset_type=preset_type,
            grade=grade,
            source="ai",
            is_active=True,
            created_by=created_by,
        )
        .order_by("-created_at")
        .first()
    )
    if cached_bank:
        cached_items = list(
            cached_bank.items.order_by("order_no").values(
                "question_text",
                "choices",
                "correct_index",
                "explanation",
                "difficulty",
            )
        )
        cached_payload = {"items": cached_items}
        valid_cached, _ = validate_quiz_payload(cached_payload)
    else:
        valid_cached = False
    if cached_bank and valid_cached:
        SQGenerationLog.objects.create(
            level="info",
            code="BANK_RAG_CACHE_HIT",
            message=f"RAG 캐시 재사용: {cached_bank.title}",
            payload={
                "bank_id": str(cached_bank.id),
                "preset_type": preset_type,
                "grade": grade,
            },
        )
        return cached_bank, True

    api_key = os.environ.get("MASTER_DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("MASTER_DEEPSEEK_API_KEY not set")

    prompt = (
        f"아래 지문만을 근거로 초등 {grade}학년 {TOPIC_LABELS.get(preset_type, '주제')} 퀴즈 3문항을 JSON으로 작성하세요.\n"
        '형식: {"items":[{"question_text":"...","choices":["A","B","C","D"],"correct_index":0,"explanation":"...","difficulty":"medium"}]}\n'
        "지문 외 추측 금지, 모르면 쉬운 수준으로 재구성하세요.\n\n"
        f"[지문]\n{normalized_source_text}"
    )

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com", timeout=8.0)
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "당신은 초등 수업용 퀴즈 생성기입니다. JSON만 출력하세요."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
    )

    payload = json.loads(resp.choices[0].message.content)
    ok, errors = validate_quiz_payload(payload)
    if not ok:
        raise ValueError(f"RAG 생성 검증 실패: {errors}")

    title = f"[RAG] {grade}학년 {TOPIC_LABELS.get(preset_type, '주제')} 맞춤 세트 {timezone.localdate().isoformat()}"
    with transaction.atomic():
        bank = SQQuizBank.objects.create(
            preset_type=preset_type,
            grade=grade,
            title=title,
            source="ai",
            is_official=False,
            is_public=False,
            share_opt_in=False,
            quality_status="approved",
            is_active=True,
            created_by=created_by,
            source_hash=source_hash,
        )
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
    SQGenerationLog.objects.create(
        level="info",
        code="BANK_RAG_CREATED",
        message=f"RAG 은행 생성: {title}",
        payload={"bank_id": str(bank.id), "preset_type": preset_type, "grade": grade},
    )
    return bank, False
