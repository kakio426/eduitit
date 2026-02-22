import json
import re
from dataclasses import dataclass
from typing import Any


MAX_STEPS = 24
MIN_STEPS = 1
MIN_TEXT_LEN = 6
MAX_TEXT_LEN = 800

TEXT_KEYS = (
    "summary",
    "text",
    "description",
    "step",
    "content",
    "activity",
    "instruction",
)
START_KEYS = ("start", "start_time", "startTime", "from")
END_KEYS = ("end", "end_time", "endTime", "to")
TIME_KEYS = ("timecode", "timestamp", "time")
MATERIAL_KEYS = ("materials", "material", "tools")
TIP_KEYS = ("teacher_tip", "tip", "note", "teacherNote")

NO_INFO_HINTS = (
    "요약할 수 있는 충분한 정보가 없습니다",
    "정보가 부족",
    "정보 부족",
)


class ManualPipelineError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass
class ParsedStep:
    text: str
    start_sec: int | None = None
    end_sec: int | None = None

    def to_display_text(self) -> str:
        prefix = ""
        if self.start_sec is not None and self.end_sec is not None:
            prefix = f"[{_format_timecode(self.start_sec)}-{_format_timecode(self.end_sec)}] "
        elif self.start_sec is not None:
            prefix = f"[{_format_timecode(self.start_sec)}] "
        return f"{prefix}{self.text}".strip()


def parse_manual_pipeline_result(raw_text: str) -> dict[str, Any]:
    if not raw_text or not str(raw_text).strip():
        raise ManualPipelineError("EMPTY_INPUT", "붙여넣은 결과가 비어 있습니다.")

    clean_input = str(raw_text).strip()
    warnings: list[str] = []

    json_payload = _extract_json_payload(clean_input)
    if json_payload is not None:
        steps = _parse_steps_from_json(json_payload, warnings)
        mode = "json"
    else:
        steps = _parse_steps_from_text(clean_input, warnings)
        mode = "plain_text"

    _validate_steps(steps)

    return {
        "steps": [
            {"id": idx, "text": step.to_display_text(), "start_sec": step.start_sec, "end_sec": step.end_sec}
            for idx, step in enumerate(steps)
        ],
        "meta": {
            "mode": mode,
            "step_count": len(steps),
        },
        "warnings": warnings,
    }


def build_manual_pipeline_prompt(video_url: str = "") -> str:
    video_line = video_url.strip() if video_url else "(여기에 유튜브 URL 입력)"
    return (
        "당신은 초등 미술 수업 설계 도우미입니다.\n"
        "아래 영상/자료를 보고 학생이 따라 하기 쉬운 단계별 수업안을 JSON으로만 출력하세요.\n\n"
        f"대상 영상 URL: {video_line}\n\n"
        "출력 규칙:\n"
        "1) 반드시 JSON만 출력 (코드블록/설명문/인사말 금지)\n"
        "2) 최상위는 객체이며 steps 배열 필수\n"
        "3) steps는 4~12개 권장, 각 step은 summary 필수\n"
        "4) 가능한 경우 start/end를 MM:SS 형식으로 포함\n"
        "5) summary는 학생 활동 중심의 짧은 문장\n"
        "6) materials는 배열, teacher_tip은 문자열\n\n"
        "JSON 스키마 예시:\n"
        "{\n"
        '  "video_title": "수업 제목",\n'
        '  "steps": [\n'
        "    {\n"
        '      "start": "00:35",\n'
        '      "end": "01:20",\n'
        '      "summary": "도화지 중앙에 큰 원을 그리고 배경 색을 고른다.",\n'
        '      "materials": ["도화지", "연필", "색연필"],\n'
        '      "teacher_tip": "선 굵기를 달리하면 입체감이 살아난다."\n'
        "    }\n"
        "  ]\n"
        "}\n"
    )


def _extract_json_payload(raw_text: str) -> Any | None:
    text = raw_text.strip()

    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    if text.startswith("{") and text.endswith("}"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            raise ManualPipelineError("INVALID_JSON", "JSON 형식이 올바르지 않습니다. 중괄호/쉼표를 확인해 주세요.")

    if text.startswith("[") and text.endswith("]"):
        try:
            return {"steps": json.loads(text)}
        except json.JSONDecodeError:
            raise ManualPipelineError("INVALID_JSON", "JSON 배열 형식이 올바르지 않습니다.")

    return None


def _parse_steps_from_json(payload: Any, warnings: list[str]) -> list[ParsedStep]:
    if not isinstance(payload, dict):
        raise ManualPipelineError("INVALID_SHAPE", "JSON 최상위는 객체 형태여야 합니다.")

    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, list):
        raise ManualPipelineError("MISSING_STEPS", "`steps` 배열이 필요합니다.")

    parsed_steps: list[ParsedStep] = []
    for idx, item in enumerate(raw_steps, start=1):
        parsed = _parse_single_step_json(item, idx, warnings)
        if parsed:
            parsed_steps.append(parsed)
    return parsed_steps


def _parse_single_step_json(item: Any, step_index: int, warnings: list[str]) -> ParsedStep | None:
    if isinstance(item, str):
        text = _normalize_spaces(item)
        if not text:
            warnings.append(f"{step_index}단계 텍스트가 비어 있어 제외했습니다.")
            return None
        return ParsedStep(text=text)

    if not isinstance(item, dict):
        warnings.append(f"{step_index}단계 형식이 올바르지 않아 제외했습니다.")
        return None

    summary = _pick_first_value(item, TEXT_KEYS)
    summary = _normalize_spaces(summary)
    if not summary:
        warnings.append(f"{step_index}단계에 설명(summary/text)이 없어 제외했습니다.")
        return None

    start_sec = _parse_time_fields(item, START_KEYS, TIME_KEYS, warnings, step_index, field_name="start")
    end_sec = _parse_time_fields(item, END_KEYS, (), warnings, step_index, field_name="end")

    if start_sec is not None and end_sec is not None and end_sec < start_sec:
        warnings.append(f"{step_index}단계 end가 start보다 빨라 시간 정보를 무시했습니다.")
        start_sec = None
        end_sec = None

    materials = _normalize_materials(_pick_first_value(item, MATERIAL_KEYS))
    teacher_tip = _normalize_spaces(_pick_first_value(item, TIP_KEYS))

    lines = [summary]
    if materials:
        lines.append(f"준비물: {', '.join(materials)}")
    if teacher_tip:
        lines.append(f"교사 팁: {teacher_tip}")

    text = lines[0]
    if len(lines) > 1:
        text += "\n- " + "\n- ".join(lines[1:])

    return ParsedStep(text=text, start_sec=start_sec, end_sec=end_sec)


def _parse_steps_from_text(raw_text: str, warnings: list[str]) -> list[ParsedStep]:
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    if not lines:
        raise ManualPipelineError("EMPTY_INPUT", "붙여넣은 결과에서 유효한 줄을 찾지 못했습니다.")

    candidates: list[str] = []
    for line in lines:
        cleaned = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
        if cleaned:
            candidates.append(cleaned)

    if not candidates:
        raise ManualPipelineError("NO_STEPS", "단계 문장을 찾지 못했습니다.")

    parsed_steps: list[ParsedStep] = []
    for idx, line in enumerate(candidates, start=1):
        start_sec, end_sec, body = _extract_inline_time_range(line)
        body = _normalize_spaces(body)
        if not body:
            warnings.append(f"{idx}번째 줄은 내용이 비어 제외했습니다.")
            continue
        parsed_steps.append(ParsedStep(text=body, start_sec=start_sec, end_sec=end_sec))

    return parsed_steps


def _pick_first_value(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in item and item[key] not in (None, ""):
            return item[key]
    return ""


def _parse_time_fields(
    item: dict[str, Any],
    primary_keys: tuple[str, ...],
    range_keys: tuple[str, ...],
    warnings: list[str],
    step_index: int,
    field_name: str,
) -> int | None:
    value = _pick_first_value(item, primary_keys)
    if value:
        sec = _to_seconds(value)
        if sec is None:
            warnings.append(f"{step_index}단계 {field_name} 시간 형식을 해석하지 못했습니다: {value}")
        return sec

    range_value = _pick_first_value(item, range_keys)
    if not range_value:
        return None

    start_sec, _, _ = _extract_inline_time_range(str(range_value))
    if start_sec is None:
        warnings.append(f"{step_index}단계 timecode 형식을 해석하지 못했습니다: {range_value}")
    return start_sec


def _extract_inline_time_range(value: str) -> tuple[int | None, int | None, str]:
    text = value.strip()
    match = re.match(
        r"^\[?\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*(?:[-~]\s*(\d{1,2}:\d{2}(?::\d{2})?))?\s*\]?\s*[:.)-]?\s*(.*)$",
        text,
    )
    if not match:
        return None, None, text

    start = _to_seconds(match.group(1))
    end = _to_seconds(match.group(2)) if match.group(2) else None
    body = match.group(3).strip()
    return start, end, body


def _to_seconds(value: Any) -> int | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        sec = int(value)
        return sec if sec >= 0 else None

    text = str(value).strip().lower()
    if not text:
        return None

    text = text.strip("[]()")
    text = text.replace(" ", "")

    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", text)
    if m and any(m.groups()):
        hours = int(m.group(1) or 0)
        minutes = int(m.group(2) or 0)
        seconds = int(m.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds

    parts = text.split(":")
    if len(parts) == 2 and all(part.isdigit() for part in parts):
        minutes, seconds = int(parts[0]), int(parts[1])
        if seconds >= 60:
            return None
        return minutes * 60 + seconds
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
        if minutes >= 60 or seconds >= 60:
            return None
        return hours * 3600 + minutes * 60 + seconds

    if text.isdigit():
        return int(text)

    return None


def _normalize_spaces(value: Any) -> str:
    text = str(value or "")
    return re.sub(r"[ \t]+", " ", text).strip()


def _normalize_materials(value: Any) -> list[str]:
    if not value:
        return []

    if isinstance(value, list):
        tokens = [str(item).strip() for item in value if str(item).strip()]
    else:
        tokens = [token.strip() for token in re.split(r"[,/|;\n]+", str(value)) if token.strip()]

    deduped: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        norm = token.lower()
        if norm in seen:
            continue
        seen.add(norm)
        deduped.append(token)
    return deduped


def _validate_steps(steps: list[ParsedStep]) -> None:
    if not steps:
        raise ManualPipelineError("NO_STEPS", "유효한 단계가 없습니다. JSON 또는 줄바꿈 형식을 확인해 주세요.")

    if len(steps) < MIN_STEPS:
        raise ManualPipelineError("TOO_FEW_STEPS", f"단계는 최소 {MIN_STEPS}개 필요합니다.")
    if len(steps) > MAX_STEPS:
        raise ManualPipelineError("TOO_MANY_STEPS", f"단계가 너무 많습니다. 최대 {MAX_STEPS}개까지 허용됩니다.")

    normalized_texts: list[str] = []
    for idx, step in enumerate(steps, start=1):
        pure_text = _normalize_spaces(step.text)
        if len(pure_text) < MIN_TEXT_LEN:
            raise ManualPipelineError("STEP_TOO_SHORT", f"{idx}단계 설명이 너무 짧습니다.")
        if len(pure_text) > MAX_TEXT_LEN:
            raise ManualPipelineError("STEP_TOO_LONG", f"{idx}단계 설명이 너무 깁니다.")

        for hint in NO_INFO_HINTS:
            if hint in pure_text:
                raise ManualPipelineError("LOW_INFO", "정보 부족 안내 문구만 포함되어 있어 단계를 만들 수 없습니다.")

        norm = re.sub(r"[^0-9a-z가-힣]+", "", pure_text.lower())
        normalized_texts.append(norm)

    duplicates = len(normalized_texts) - len(set(normalized_texts))
    if duplicates > max(1, len(steps) // 3):
        raise ManualPipelineError("DUPLICATED_STEPS", "중복된 단계가 너무 많습니다. 결과를 다시 생성해 주세요.")


def _format_timecode(total_seconds: int) -> str:
    total_seconds = max(0, int(total_seconds))
    hours, rem = divmod(total_seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"
