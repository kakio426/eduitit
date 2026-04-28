import json
import re


FIELD_KIND_LABELS = {
    "short_text": "짧은 글",
    "long_text": "긴 글",
    "secret": "비밀 입력",
    "file": "파일",
    "link": "링크",
    "single_choice": "선택",
    "multi_choice": "복수 선택",
}

TEXT_FIELD_KINDS = {"short_text", "long_text", "secret"}
CHOICE_FIELD_KINDS = {"single_choice", "multi_choice"}
FIELD_KINDS = set(FIELD_KIND_LABELS)
MAX_FIELD_COUNT = 12
MAX_OPTION_COUNT = 12


def _clean_text(value, *, max_length=120):
    text = str(value or "").strip()
    return text[:max_length]


def _clean_id(value, fallback):
    candidate = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value or "").strip()).strip("_").lower()
    if not candidate:
        candidate = fallback
    return candidate[:40]


def normalize_field_schema(raw_schema):
    if isinstance(raw_schema, str):
        try:
            raw_schema = json.loads(raw_schema)
        except json.JSONDecodeError:
            raw_schema = []
    if not isinstance(raw_schema, list):
        return []

    normalized = []
    seen_ids = set()
    for index, raw_item in enumerate(raw_schema[:MAX_FIELD_COUNT], start=1):
        if not isinstance(raw_item, dict):
            continue

        kind = _clean_text(raw_item.get("kind"), max_length=40)
        if kind not in FIELD_KINDS:
            kind = "short_text"

        label = _clean_text(raw_item.get("label"), max_length=80)
        if not label:
            label = FIELD_KIND_LABELS[kind]

        field_id = _clean_id(raw_item.get("id"), f"field_{index}")
        base_id = field_id
        suffix = 2
        while field_id in seen_ids:
            field_id = f"{base_id}_{suffix}"[:40]
            suffix += 1
        seen_ids.add(field_id)

        options = []
        if kind in CHOICE_FIELD_KINDS:
            raw_options = raw_item.get("options", [])
            if isinstance(raw_options, str):
                raw_options = raw_options.splitlines()
            if isinstance(raw_options, list):
                seen_options = set()
                for raw_option in raw_options[:MAX_OPTION_COUNT]:
                    option = _clean_text(raw_option, max_length=80)
                    if option and option not in seen_options:
                        options.append(option)
                        seen_options.add(option)

        normalized.append(
            {
                "id": field_id,
                "label": label,
                "kind": kind,
                "required": bool(raw_item.get("required", True)),
                "options": options,
            }
        )

    return normalized


def schema_uses_file(schema):
    return any(item.get("kind") == "file" for item in normalize_field_schema(schema))


def schema_uses_link(schema):
    return any(item.get("kind") == "link" for item in normalize_field_schema(schema))


def schema_uses_text(schema):
    return any(item.get("kind") in TEXT_FIELD_KINDS for item in normalize_field_schema(schema))


def schema_uses_choice(schema):
    return any(item.get("kind") in CHOICE_FIELD_KINDS for item in normalize_field_schema(schema))
