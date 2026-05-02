import re


DOCUMENT_SCHEMA_VERSION = "document-spec-v2"

DOCUMENT_PROMPT_VERSION = "document-spec-v2"

ALLOWED_BLOCK_TYPES = {
    "masthead",
    "title",
    "meta_table",
    "paragraph",
    "bullet_list",
    "info_table",
    "schedule_table",
    "decision_table",
    "budget_table",
    "callout_box",
    "signature_box",
}

TABLE_BLOCK_TYPES = {"meta_table", "info_table", "schedule_table", "decision_table", "budget_table"}

DOCUMENT_OPTION_CHOICES = [
    {"value": "schedule", "label": "일정표"},
    {"value": "preparation", "label": "준비물"},
    {"value": "contact", "label": "문의"},
    {"value": "signature", "label": "서명란"},
    {"value": "budget", "label": "예산"},
]

OPTION_CODES = {item["value"] for item in DOCUMENT_OPTION_CHOICES}

DOCUMENT_TYPE_LABELS = {
    "notice": "안내문",
    "home_letter": "가정통신문",
    "plan": "계획안",
    "minutes": "회의록",
    "report": "보고서",
    "freeform": "자유 문서",
}

DEFAULT_OPTIONS_BY_TYPE = {
    "notice": {"schedule", "preparation", "contact"},
    "home_letter": {"schedule", "preparation", "contact", "signature"},
    "plan": {"schedule", "budget", "signature"},
    "minutes": {"signature"},
    "report": {"budget", "signature"},
    "freeform": {"preparation", "contact"},
}

TABLE_DEFAULTS = {
    "meta_table": {
        "title": "문서 정보",
        "headers": ["항목", "내용"],
        "rows": [["대상", "확인 필요"], ["일시", "확인 필요"]],
    },
    "info_table": {
        "title": "핵심 안내",
        "headers": ["항목", "내용"],
        "rows": [["주요 내용", "확인 필요"], ["확인 사항", "확인 필요"]],
    },
    "schedule_table": {
        "title": "일정",
        "headers": ["일자", "시간", "내용"],
        "rows": [["확인 필요", "확인 필요", "확인 필요"]],
    },
    "decision_table": {
        "title": "결정 사항",
        "headers": ["안건", "결정", "담당"],
        "rows": [["확인 필요", "확인 필요", "확인 필요"]],
    },
    "budget_table": {
        "title": "예산",
        "headers": ["항목", "금액", "비고"],
        "rows": [["확인 필요", "확인 필요", "확인 필요"]],
    },
}


def normalize_feature_codes(values):
    if values is None:
        return []
    if isinstance(values, str):
        values = re.split(r"[, ]+", values.strip()) if values.strip() else []
    result = []
    for value in values:
        code = str(value or "").strip()
        if code in OPTION_CODES and code not in result:
            result.append(code)
    return result


def infer_document_type(document_type, prompt):
    normalized_type = str(document_type or "").strip() or "freeform"
    if normalized_type != "freeform":
        return normalized_type if normalized_type in DOCUMENT_TYPE_LABELS else "notice"

    text = str(prompt or "")
    if re.search(r"회의|협의|안건|결정|참석", text):
        return "minutes"
    if re.search(r"보고|결과|실적|평가|환류", text):
        return "report"
    if re.search(r"계획|운영|추진|프로그램|예산", text):
        return "plan"
    if re.search(r"가정통신문|학부모|보호자|가정", text):
        return "home_letter"
    return "notice"


def normalize_document_spec(payload, *, document_type, prompt, selected_blocks=None):
    effective_type = infer_document_type(document_type, prompt)
    option_codes = normalize_feature_codes(selected_blocks)
    if not option_codes:
        option_codes = sorted(DEFAULT_OPTIONS_BY_TYPE.get(effective_type, DEFAULT_OPTIONS_BY_TYPE["freeform"]))

    source = payload if isinstance(payload, dict) else {}
    if source.get("schema_version") != DOCUMENT_SCHEMA_VERSION or not isinstance(source.get("blocks"), list):
        source = legacy_payload_to_spec(source, document_type=effective_type, prompt=prompt, selected_blocks=option_codes)

    title = clean_text(source.get("title"), limit=80) or f"{DOCUMENT_TYPE_LABELS.get(effective_type, '문서')} 초안"
    subtitle = clean_text(source.get("subtitle"), limit=100)
    summary_text = clean_text(source.get("summary_text"), limit=160) or title
    normalized_blocks = []
    for block in source.get("blocks") or []:
        normalized = normalize_block(block, title=title)
        if normalized:
            normalized_blocks.append(normalized)

    spec = {
        "schema_version": DOCUMENT_SCHEMA_VERSION,
        "document_type": effective_type,
        "selected_blocks": option_codes,
        "title": title,
        "subtitle": subtitle,
        "summary_text": summary_text,
        "blocks": normalized_blocks,
    }
    spec["blocks"] = ensure_required_blocks(spec, prompt=prompt)
    return spec


def legacy_payload_to_spec(payload, *, document_type, prompt, selected_blocks=None):
    source = payload if isinstance(payload, dict) else {}
    title = clean_text(source.get("title"), limit=80) or f"{DOCUMENT_TYPE_LABELS.get(document_type, '문서')} 초안"
    subtitle = clean_text(source.get("subtitle"), limit=100)
    summary_text = clean_text(source.get("summary_text"), limit=160)
    meta_rows = meta_lines_to_rows(source.get("meta_lines"))
    body_blocks = source.get("body_blocks") if isinstance(source.get("body_blocks"), list) else []
    paragraphs = []
    bullets = []
    info_rows = []

    for block in body_blocks[:8]:
        if not isinstance(block, dict):
            text = clean_text(block, limit=420)
            if text:
                paragraphs.append(text)
            continue
        heading = clean_text(block.get("heading"), limit=80)
        block_paragraphs = [clean_text(item, limit=300) for item in as_list(block.get("paragraphs") or block.get("body"))]
        block_bullets = [clean_text(item, limit=120) for item in as_list(block.get("bullets"))]
        block_paragraphs = [item for item in block_paragraphs if item]
        block_bullets = [item for item in block_bullets if item]
        if heading and block_paragraphs:
            info_rows.append([heading, block_paragraphs[0]])
        elif heading:
            paragraphs.append(heading)
        paragraphs.extend(block_paragraphs[:2])
        bullets.extend(block_bullets[:5])

    if not paragraphs:
        fallback = clean_text(prompt, limit=300)
        if fallback:
            paragraphs.append(fallback)

    option_codes = set(normalize_feature_codes(selected_blocks))
    blocks = [
        default_masthead_block(),
        {"type": "title", "text": title, "subtitle": subtitle},
        table_block("meta_table", rows=meta_rows),
        {
            "type": "paragraph",
            "title": primary_paragraph_title(document_type),
            "text": "\n".join(paragraphs[:4]),
        },
    ]

    if info_rows:
        blocks.append(table_block("info_table", rows=info_rows[:6]))
    if "preparation" in option_codes or bullets:
        blocks.append({"type": "bullet_list", "title": "준비와 확인", "items": bullets[:8] or ["확인 필요"]})
    if "schedule" in option_codes:
        blocks.append(table_block("schedule_table"))
    if "budget" in option_codes:
        blocks.append(table_block("budget_table"))
    if "contact" in option_codes:
        blocks.append({"type": "callout_box", "title": "문의", "text": "담당 부서 또는 담임 선생님께 문의해 주세요."})

    closing = clean_text(source.get("closing"), limit=240)
    if closing:
        blocks.append({"type": "paragraph", "title": "마무리", "text": closing})
    if "signature" in option_codes:
        blocks.append({"type": "signature_box", "date": "20  .  .", "signer": "○○학교장"})

    return {
        "schema_version": DOCUMENT_SCHEMA_VERSION,
        "document_type": document_type,
        "selected_blocks": normalize_feature_codes(selected_blocks),
        "title": title,
        "subtitle": subtitle,
        "summary_text": summary_text or (paragraphs[0] if paragraphs else title),
        "blocks": blocks,
    }


def ensure_required_blocks(spec, *, prompt):
    document_type = spec.get("document_type") or "notice"
    option_codes = set(spec.get("selected_blocks") or [])
    blocks = list(spec.get("blocks") or [])
    if not any(block.get("type") == "masthead" for block in blocks):
        blocks.insert(0, default_masthead_block())
    if not any(block.get("type") == "title" for block in blocks):
        blocks.insert(1, {"type": "title", "text": spec.get("title") or "문서 초안", "subtitle": spec.get("subtitle") or ""})
    if not any(block.get("type") == "meta_table" for block in blocks):
        blocks.append(table_block("meta_table"))
    if not any(block.get("type") == "paragraph" for block in blocks):
        blocks.append(
            {
                "type": "paragraph",
                "title": primary_paragraph_title(document_type),
                "text": clean_text(prompt, limit=300) or "요청한 내용을 바탕으로 정리했습니다.",
            }
        )

    existing_types = {block.get("type") for block in blocks}
    if document_type in {"notice", "home_letter"}:
        if "schedule" in option_codes and "schedule_table" not in existing_types:
            blocks.append(table_block("schedule_table"))
        if "preparation" in option_codes and "bullet_list" not in existing_types:
            blocks.append({"type": "bullet_list", "title": "준비와 확인", "items": ["확인 필요"]})
        if "contact" in option_codes and "callout_box" not in existing_types:
            blocks.append({"type": "callout_box", "title": "문의", "text": "담당 부서 또는 담임 선생님께 문의해 주세요."})
        if "signature" in option_codes and "signature_box" not in existing_types:
            blocks.append({"type": "signature_box", "date": "20  .  .", "signer": "○○학교장"})
    elif document_type == "plan":
        if "schedule_table" not in existing_types:
            blocks.append(table_block("schedule_table"))
        if "info_table" not in existing_types:
            blocks.append(table_block("info_table", title="운영 내용"))
        if "budget" in option_codes and "budget_table" not in existing_types:
            blocks.append(table_block("budget_table"))
        if "callout_box" not in existing_types:
            blocks.append({"type": "callout_box", "title": "안전과 평가", "text": "운영 전 안전 사항과 평가 방법을 확인합니다."})
    elif document_type == "minutes":
        if "decision_table" not in existing_types:
            blocks.append(table_block("decision_table"))
        if "info_table" not in existing_types:
            blocks.append(table_block("info_table", title="후속 할 일", headers=["할 일", "담당", "기한"]))
    elif document_type == "report":
        if "info_table" not in existing_types:
            blocks.append(table_block("info_table", title="추진 결과"))
        if "budget" in option_codes and "budget_table" not in existing_types:
            blocks.append(table_block("budget_table"))
        if "callout_box" not in existing_types:
            blocks.append({"type": "callout_box", "title": "개선안", "text": "다음 운영에 반영할 사항을 정리합니다."})

    if "signature" in option_codes and not any(block.get("type") == "signature_box" for block in blocks):
        blocks.append({"type": "signature_box", "date": "20  .  .", "signer": "○○학교장"})
    return blocks[:18]


def normalize_block(block, *, title):
    if not isinstance(block, dict):
        return None
    block_type = str(block.get("type") or "").strip()
    if block_type not in ALLOWED_BLOCK_TYPES:
        return None
    if block_type == "masthead":
        return {
            "type": "masthead",
            "school_name": clean_text(block.get("school_name"), limit=80) or "○○학교",
            "department": clean_text(block.get("department"), limit=80),
            "contact": clean_text(block.get("contact"), limit=80) or "교무실 000-0000-0000",
            "fax": clean_text(block.get("fax"), limit=80),
        }
    if block_type == "title":
        return {
            "type": "title",
            "text": clean_text(block.get("text") or block.get("title"), limit=80) or title,
            "subtitle": clean_text(block.get("subtitle"), limit=100),
        }
    if block_type == "paragraph":
        text = clean_text(block.get("text") or block.get("content") or "\n".join(as_list(block.get("paragraphs"))), limit=900)
        if not text:
            return None
        return {
            "type": "paragraph",
            "title": clean_text(block.get("title") or block.get("heading"), limit=80),
            "text": text,
        }
    if block_type == "bullet_list":
        items = [clean_text(item, limit=120) for item in as_list(block.get("items") or block.get("bullets"))]
        items = [item for item in items if item][:8]
        if not items:
            items = ["확인 필요"]
        return {
            "type": "bullet_list",
            "title": clean_text(block.get("title") or block.get("heading"), limit=80) or "확인 사항",
            "items": items,
        }
    if block_type in TABLE_BLOCK_TYPES:
        return normalize_table_block(block_type, block)
    if block_type == "callout_box":
        text = clean_text(block.get("text") or block.get("content"), limit=260)
        if not text:
            text = "확인 필요"
        return {
            "type": "callout_box",
            "title": clean_text(block.get("title"), limit=60) or "확인",
            "text": text,
        }
    if block_type == "signature_box":
        return {
            "type": "signature_box",
            "date": clean_text(block.get("date"), limit=40) or "20  .  .",
            "signer": clean_text(block.get("signer"), limit=80) or "○○학교장",
            "note": clean_text(block.get("note"), limit=80),
        }
    return None


def normalize_table_block(block_type, block):
    defaults = TABLE_DEFAULTS[block_type]
    headers = [clean_text(item, limit=30) for item in as_list(block.get("headers"))]
    headers = [item for item in headers if item][:5] or list(defaults["headers"])
    rows = normalize_table_rows(block.get("rows"), headers)
    if not rows:
        rows = normalize_table_rows(defaults["rows"], headers)
    return {
        "type": block_type,
        "title": clean_text(block.get("title"), limit=80) or defaults["title"],
        "headers": headers,
        "rows": rows[:8],
    }


def normalize_table_rows(value, headers):
    rows = []
    if isinstance(value, dict):
        value = [[key, item] for key, item in value.items()]
    if not isinstance(value, list):
        return rows
    for row in value:
        if isinstance(row, dict):
            cells = [row.get(header, row.get(str(index), "")) for index, header in enumerate(headers)]
        else:
            cells = as_list(row)
        normalized_cells = [clean_text(cell, limit=110) or "확인 필요" for cell in cells[: len(headers)]]
        while len(normalized_cells) < len(headers):
            normalized_cells.append("확인 필요")
        if any(cell and cell != "확인 필요" for cell in normalized_cells) or normalized_cells:
            rows.append(normalized_cells)
        if len(rows) >= 8:
            break
    return rows


def validate_document_spec(spec, *, page_count=None):
    issues = []
    if not isinstance(spec, dict) or spec.get("schema_version") != DOCUMENT_SCHEMA_VERSION:
        return ["문서 스키마가 올바르지 않습니다."]
    title = str(spec.get("title") or "")
    if len(title) > 80:
        issues.append("제목이 너무 깁니다.")
    blocks = spec.get("blocks") if isinstance(spec.get("blocks"), list) else []
    block_types = {block.get("type") for block in blocks if isinstance(block, dict)}
    for required in ("masthead", "title", "meta_table", "paragraph"):
        if required not in block_types:
            issues.append(f"{required} 블록이 없습니다.")
    for block in blocks:
        if not isinstance(block, dict):
            issues.append("알 수 없는 블록이 있습니다.")
            continue
        block_type = block.get("type")
        if block_type not in ALLOWED_BLOCK_TYPES:
            issues.append(f"지원하지 않는 블록입니다: {block_type}")
        if block_type in TABLE_BLOCK_TYPES:
            headers = block.get("headers") or []
            rows = block.get("rows") or []
            if len(headers) > 5:
                issues.append("표 열은 5개 이하여야 합니다.")
            if not rows:
                issues.append("빈 표가 있습니다.")
            for row in rows:
                for cell in row:
                    if len(str(cell or "")) > 110:
                        issues.append("표 셀 내용이 너무 깁니다.")
                        break
    if page_count and spec.get("document_type") in {"notice", "home_letter"} and int(page_count) > 2:
        issues.append("안내문과 가정통신문은 2쪽 안쪽이어야 합니다.")
    return issues


def table_block(block_type, *, title=None, headers=None, rows=None):
    defaults = TABLE_DEFAULTS[block_type]
    return normalize_table_block(
        block_type,
        {
            "title": title or defaults["title"],
            "headers": headers or defaults["headers"],
            "rows": rows or defaults["rows"],
        },
    )


def default_masthead_block():
    return {
        "type": "masthead",
        "school_name": "○○학교",
        "department": "",
        "contact": "교무실 000-0000-0000",
        "fax": "",
    }


def meta_lines_to_rows(lines):
    rows = []
    for item in as_list(lines)[:6]:
        text = clean_text(item, limit=90)
        if not text:
            continue
        if ":" in text:
            label, value = text.split(":", 1)
        elif "：" in text:
            label, value = text.split("：", 1)
        else:
            label, value = "내용", text
        rows.append([clean_text(label, limit=30) or "항목", clean_text(value, limit=110) or "확인 필요"])
    return rows or TABLE_DEFAULTS["meta_table"]["rows"]


def primary_paragraph_title(document_type):
    if document_type == "home_letter":
        return "안내"
    if document_type == "plan":
        return "목적"
    if document_type == "minutes":
        return "논의 내용"
    if document_type == "report":
        return "개요"
    return "내용"


def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def clean_text(value, *, limit):
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:limit].strip()
