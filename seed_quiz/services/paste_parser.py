import csv
import io
import json
import re

from seed_quiz.services.bank import CSV_HEADER_ALIAS_MAP

CANONICAL_HEADERS = [
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
]

HEADER_SET = set(CANONICAL_HEADERS)


def _canonical_header(name: str) -> str:
    key = str(name or "").strip().lower()
    if not key:
        return ""
    return CSV_HEADER_ALIAS_MAP.get(key, key)


def _clean_text(raw_text: str) -> str:
    text = (raw_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()
    return text


def _looks_like_json(text: str) -> bool:
    stripped = text.lstrip()
    return stripped.startswith("{") or stripped.startswith("[")


def _normalize_correct_index(raw_value) -> str:
    value = str(raw_value or "").strip()
    if not value:
        return ""
    try:
        num = int(value)
    except ValueError:
        return value
    if num in (1, 2, 3, 4):
        return str(num)
    return str(num)


def _normalize_correct_index_json(raw_value) -> str:
    value = str(raw_value or "").strip()
    if not value:
        return ""
    try:
        num = int(value)
    except ValueError:
        return value
    if num in (0, 1, 2, 3):
        return str(num + 1)
    if num in (1, 2, 3, 4):
        return str(num)
    return str(num)


def _dict_to_canonical_row(raw: dict, fallback_preset: str = "", fallback_grade: str = "") -> dict:
    row = {key: "" for key in CANONICAL_HEADERS}
    for k, v in (raw or {}).items():
        canonical = _canonical_header(k)
        if canonical in row:
            row[canonical] = "" if v is None else str(v).strip()

    # JSON 전용 보정: choices 배열 지원
    choices = raw.get("choices") if isinstance(raw, dict) else None
    if isinstance(choices, list):
        for idx in range(4):
            key = f"choice_{idx + 1}"
            if idx < len(choices) and not row[key]:
                row[key] = "" if choices[idx] is None else str(choices[idx]).strip()

    # JSON 전용 보정: topic 키 지원
    if not row["preset_type"]:
        row["preset_type"] = str(raw.get("topic") or fallback_preset or "").strip()
    if not row["grade"]:
        row["grade"] = str(raw.get("grade") or fallback_grade or "").strip()

    row["correct_index"] = _normalize_correct_index_json(row["correct_index"] or raw.get("answer"))
    return row


def _parse_json_rows(text: str) -> tuple[list[dict], list[str]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as e:
        return [], [f"JSON 파싱 실패: {e}"]

    rows = []
    if isinstance(payload, list):
        for item in payload:
            if not isinstance(item, dict):
                continue
            rows.append(_dict_to_canonical_row(item))
        return rows, []

    if not isinstance(payload, dict):
        return [], ["JSON 형식이 올바르지 않습니다. 객체 또는 배열이어야 합니다."]

    # {"items":[...], "preset_type":"...", "grade":3} 형태 지원
    items = payload.get("items")
    fallback_preset = str(payload.get("preset_type") or payload.get("topic") or "").strip()
    fallback_grade = str(payload.get("grade") or "").strip()
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            rows.append(_dict_to_canonical_row(item, fallback_preset=fallback_preset, fallback_grade=fallback_grade))
        return rows, []

    return [], ["JSON에는 rows/items 배열이 있어야 합니다."]


def _parse_markdown_table(text: str) -> list[list[str]]:
    rows = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "|" not in line:
            continue
        if re.fullmatch(r"\|?[\s:\-|\t]+\|?", line):
            continue
        if line.startswith("|"):
            line = line[1:]
        if line.endswith("|"):
            line = line[:-1]
        cells = [cell.strip() for cell in line.split("|")]
        rows.append(cells)
    return rows


def _parse_delimited_rows(text: str, delimiter: str) -> list[list[str]]:
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    return [row for row in reader]


def _parse_stacked_lines_rows(text: str) -> tuple[list[dict], list[str]]:
    """
    한 줄에 한 칸씩 세로로 나열된 텍스트를 파싱한다.
    예)
    주제
    학년
    문제
    ...
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 20:
        return [], ["세로 나열 형식으로 볼 수 있는 충분한 데이터가 없습니다."]

    header_candidates = lines[: len(CANONICAL_HEADERS)]
    normalized_header = [_canonical_header(h) for h in header_candidates]
    if any(h not in HEADER_SET for h in normalized_header):
        return [], ["세로 나열 형식의 헤더를 인식하지 못했습니다."]

    data_values = lines[len(CANONICAL_HEADERS) :]
    field_count = len(CANONICAL_HEADERS)
    if len(data_values) % field_count != 0:
        return [], ["세로 나열 형식의 데이터 개수가 열 개수(10)의 배수가 아닙니다."]

    rows: list[dict] = []
    for start in range(0, len(data_values), field_count):
        chunk = data_values[start : start + field_count]
        row = {key: "" for key in CANONICAL_HEADERS}
        for idx, value in enumerate(chunk):
            canonical = normalized_header[idx]
            if canonical in HEADER_SET:
                row[canonical] = str(value or "").strip()
        row["correct_index"] = _normalize_correct_index(row["correct_index"])
        rows.append(row)
    return rows, []


def _build_rows_from_text(text: str) -> tuple[list[dict], str, list[str]]:
    if _looks_like_json(text):
        json_rows, json_errors = _parse_json_rows(text)
        if json_errors:
            return [], "json", json_errors
        return json_rows, "json", []

    markdown_rows = _parse_markdown_table(text)
    if len(markdown_rows) >= 2:
        raw_rows = markdown_rows
        source_format = "markdown_table"
    else:
        lines = text.splitlines()
        first_line = lines[0] if lines else ""
        second_line = lines[1] if len(lines) > 1 else ""
        if ("\t" not in first_line and "," not in first_line) and ("\t" not in second_line and "," not in second_line):
            stacked_rows, stacked_errors = _parse_stacked_lines_rows(text)
            if not stacked_errors:
                return stacked_rows, "stacked_lines", []
            return [], "stacked_lines", stacked_errors

        delimiter = "\t" if "\t" in first_line else ","
        source_format = "tsv" if delimiter == "\t" else "csv_text"
        raw_rows = _parse_delimited_rows(text, delimiter=delimiter)

    if not raw_rows:
        return [], source_format, ["붙여넣은 텍스트에서 행을 찾을 수 없습니다."]

    normalized_header = [_canonical_header(h) for h in raw_rows[0]]
    header_hit_count = sum(1 for h in normalized_header if h in HEADER_SET)
    has_header = header_hit_count >= 5 and "question_text" in normalized_header

    data_rows = raw_rows[1:] if has_header else raw_rows
    rows: list[dict] = []
    for raw in data_rows:
        if not raw or not any(str(v or "").strip() for v in raw):
            continue
        row = {key: "" for key in CANONICAL_HEADERS}
        if has_header:
            for idx, value in enumerate(raw):
                if idx >= len(normalized_header):
                    continue
                canonical = normalized_header[idx]
                if canonical in HEADER_SET:
                    row[canonical] = "" if value is None else str(value).strip()
        else:
            for idx, key in enumerate(CANONICAL_HEADERS):
                if idx < len(raw):
                    row[key] = "" if raw[idx] is None else str(raw[idx]).strip()
        row["correct_index"] = _normalize_correct_index(row["correct_index"])
        rows.append(row)

    if not rows:
        return [], source_format, ["붙여넣은 텍스트에서 유효한 데이터 행을 찾을 수 없습니다."]

    return rows, source_format, []


def parse_pasted_text_to_csv_bytes(raw_text: str) -> tuple[bytes | None, str, list[str]]:
    """
    붙여넣기 텍스트(TSV/CSV/Markdown Table/JSON)를
    Seed Quiz 표준 CSV 바이트로 변환한다.
    """
    text = _clean_text(raw_text)
    if not text:
        return None, "empty", ["붙여넣기 내용이 비어 있습니다."]

    rows, source_format, errors = _build_rows_from_text(text)
    if errors:
        return None, source_format, errors

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CANONICAL_HEADERS)
    for row in rows:
        writer.writerow([row.get(col, "") for col in CANONICAL_HEADERS])
    return output.getvalue().encode("utf-8"), source_format, []
