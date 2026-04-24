import os
import re
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from django.db import transaction

from .models import DocAnalysis, DocAssistantQuestion


ASSISTANT_ENGINE_VERSION = "doccollab-local-v1"
SUPPORTED_SUFFIXES = {".hwp", ".hwpx"}
MAX_DOCUMENT_BYTES = 15 * 1024 * 1024
MAX_MARKDOWN_CHARS = 120000
MAX_CHUNK_CHARS = 1200
MAX_QUESTIONS_PER_ANALYSIS = 40
ACTION_KEYWORDS = (
    "제출",
    "신청",
    "마감",
    "기한",
    "준비",
    "참석",
    "회신",
    "등록",
    "업로드",
    "배부",
    "안내",
    "협조",
    "필수",
)
DATE_PATTERN = re.compile(
    r"(?P<date>(?:20\d{2}[-./년]\s*)?\d{1,2}\s*(?:[-./월])\s*\d{1,2}\s*(?:일)?)"
)


class DocumentAssistantError(Exception):
    def __init__(self, message, *, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def current_analysis_for_revision(room, revision):
    if revision is None:
        return None
    return (
        room.analyses.filter(source_revision=revision)
        .select_related("source_revision")
        .order_by("-updated_at")
        .first()
    )


def serialize_analysis(analysis):
    if analysis is None:
        return None
    payload = analysis.parse_payload if isinstance(analysis.parse_payload, dict) else {}
    return {
        "id": str(analysis.id),
        "status": analysis.status,
        "status_label": analysis.get_status_display(),
        "engine": analysis.engine,
        "summary_text": analysis.summary_text,
        "error_message": analysis.error_message,
        "source_revision_id": str(analysis.source_revision_id or ""),
        "work_items": list(payload.get("work_items") or [])[:12],
        "chunks": list(payload.get("chunks") or [])[:8],
        "char_count": int(payload.get("char_count") or len(analysis.raw_markdown or "")),
        "updated_at": analysis.updated_at.isoformat(),
    }


def serialize_question(question, *, reused=False):
    return {
        "id": str(question.id),
        "question": question.question,
        "answer": question.answer,
        "citations": question.citations_json or [],
        "has_insufficient_evidence": question.has_insufficient_evidence,
        "reused": reused,
    }


def analyze_revision(*, room, revision, user):
    if revision is None:
        raise DocumentAssistantError("정리할 문서가 없습니다.", status_code=400)

    with transaction.atomic():
        analysis, _created = DocAnalysis.objects.select_for_update().get_or_create(
            room=room,
            source_revision=revision,
            defaults={
                "status": DocAnalysis.Status.PROCESSING,
                "created_by": user,
            },
        )
    if analysis.status == DocAnalysis.Status.READY and analysis.raw_markdown:
        return analysis, True

    try:
        raw_bytes = _read_revision_bytes(revision)
        markdown, engine = extract_document_markdown(raw_bytes, revision.original_name)
        parsed = build_parse_payload(markdown, file_name=revision.original_name, engine=engine)
    except DocumentAssistantError as exc:
        analysis.status = DocAnalysis.Status.FAILED
        analysis.engine = ASSISTANT_ENGINE_VERSION
        analysis.raw_markdown = ""
        analysis.parse_payload = {}
        analysis.summary_text = ""
        analysis.error_message = exc.message[:200]
        analysis.created_by = analysis.created_by or user
        analysis.save(
            update_fields=[
                "status",
                "engine",
                "raw_markdown",
                "parse_payload",
                "summary_text",
                "error_message",
                "created_by",
                "updated_at",
            ]
        )
        raise

    analysis.status = DocAnalysis.Status.READY
    analysis.engine = engine
    analysis.raw_markdown = markdown
    analysis.parse_payload = parsed
    analysis.summary_text = parsed["summary_text"][:200]
    analysis.error_message = ""
    analysis.created_by = analysis.created_by or user
    analysis.save(
        update_fields=[
            "status",
            "engine",
            "raw_markdown",
            "parse_payload",
            "summary_text",
            "error_message",
            "created_by",
            "updated_at",
        ]
    )
    return analysis, False


def answer_analysis_question(*, analysis, user, question):
    if analysis is None or analysis.status != DocAnalysis.Status.READY:
        raise DocumentAssistantError("먼저 AI 정리를 실행해 주세요.", status_code=400)
    cleaned_question = normalize_question(question)
    if not cleaned_question:
        raise DocumentAssistantError("질문을 입력해 주세요.", status_code=400)

    cached = analysis.questions.filter(
        normalized_question=cleaned_question,
        provider=ASSISTANT_ENGINE_VERSION,
    ).first()
    if cached is not None:
        return cached, True
    if analysis.questions.filter(provider=ASSISTANT_ENGINE_VERSION).count() >= MAX_QUESTIONS_PER_ANALYSIS:
        raise DocumentAssistantError("질문이 많습니다. 잠시 후 다시 시도해 주세요.", status_code=429)

    chunks = find_relevant_chunks(analysis.parse_payload, cleaned_question)
    if not chunks:
        question_obj = DocAssistantQuestion.objects.create(
            analysis=analysis,
            created_by=user,
            question=question[:300],
            normalized_question=cleaned_question,
            answer="문서 근거를 찾지 못했습니다.",
            citations_json=[],
            has_insufficient_evidence=True,
            provider=ASSISTANT_ENGINE_VERSION,
        )
        return question_obj, False

    citations = [
        {
            "chunk_id": chunk.get("id"),
            "label": chunk.get("section_label") or "본문",
            "text": _excerpt(chunk.get("text") or chunk.get("markdown") or "", limit=180),
        }
        for chunk in chunks[:3]
    ]
    answer = compose_answer(cleaned_question, chunks)
    question_obj = DocAssistantQuestion.objects.create(
        analysis=analysis,
        created_by=user,
        question=question[:300],
        normalized_question=cleaned_question,
        answer=answer,
        citations_json=citations,
        has_insufficient_evidence=False,
        provider=ASSISTANT_ENGINE_VERSION,
    )
    return question_obj, False


def extract_document_markdown(raw_bytes, file_name):
    suffix = Path(str(file_name or "")).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise DocumentAssistantError("HWP 또는 HWPX 파일만 정리합니다.", status_code=400)
    try:
        import unhwp
    except ImportError:
        unhwp = None

    if unhwp is not None:
        temp_path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix or ".hwp", delete=False) as temp_file:
                temp_file.write(raw_bytes)
                temp_path = temp_file.name
            markdown = str(unhwp.to_markdown(temp_path) or "").strip()
        except Exception as exc:
            if suffix == ".hwpx":
                markdown = _extract_hwpx_markdown(raw_bytes)
                return markdown[:MAX_MARKDOWN_CHARS], "doccollab-hwpx-fallback"
            raise DocumentAssistantError("문서를 정리하지 못했습니다. 파일을 확인해 주세요.", status_code=400) from exc
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
        if not markdown:
            if suffix == ".hwpx":
                markdown = _extract_hwpx_markdown(raw_bytes)
                return markdown[:MAX_MARKDOWN_CHARS], "doccollab-hwpx-fallback"
            raise DocumentAssistantError("읽을 수 있는 글을 찾지 못했습니다.", status_code=400)
        return markdown[:MAX_MARKDOWN_CHARS], "unhwp"

    if suffix == ".hwpx":
        markdown = _extract_hwpx_markdown(raw_bytes)
        return markdown[:MAX_MARKDOWN_CHARS], "doccollab-hwpx-fallback"

    raise DocumentAssistantError("HWP 분석 엔진을 준비하지 못했습니다.", status_code=503)


def build_parse_payload(markdown, *, file_name, engine):
    text = str(markdown or "").strip()
    if not text:
        raise DocumentAssistantError("읽을 수 있는 글을 찾지 못했습니다.", status_code=400)
    if len(text) > MAX_MARKDOWN_CHARS:
        raise DocumentAssistantError("문서가 너무 깁니다. 나눠서 올려 주세요.", status_code=400)

    blocks = build_blocks(text)
    chunks = build_chunks(blocks)
    work_items = build_work_items(blocks)
    summary_text = summarize_document(text, file_name=file_name)
    return {
        "engine": engine,
        "file_name": file_name,
        "summary_text": summary_text,
        "char_count": len(text),
        "blocks": blocks[:160],
        "chunks": chunks,
        "work_items": work_items,
    }


def build_blocks(markdown):
    blocks = []
    for index, raw_block in enumerate(re.split(r"\n{2,}", str(markdown or "").strip()), start=1):
        text = _normalize_text(raw_block)
        if not text:
            continue
        kind = "table" if "|" in raw_block and "---" in raw_block else "text"
        blocks.append(
            {
                "id": f"block-{index}",
                "kind": kind,
                "section_label": "표" if kind == "table" else "본문",
                "text": text,
                "markdown": raw_block.strip(),
            }
        )
    return blocks


def build_chunks(blocks):
    chunks = []
    current = []
    current_length = 0

    def flush():
        nonlocal current, current_length
        if not current:
            return
        chunk_index = len(chunks) + 1
        text = "\n\n".join(block["text"] for block in current if block.get("text")).strip()
        markdown = "\n\n".join(block["markdown"] for block in current if block.get("markdown")).strip()
        chunks.append(
            {
                "id": f"chunk-{chunk_index}",
                "section_label": current[0].get("section_label") or "본문",
                "text": text,
                "markdown": markdown,
                "block_ids": [block["id"] for block in current if block.get("id")],
                "has_evidence": any(block.get("kind") == "table" for block in current),
            }
        )
        current = []
        current_length = 0

    for block in blocks:
        block_text = block.get("text") or ""
        projected = current_length + len(block_text)
        if current and projected > MAX_CHUNK_CHARS:
            flush()
        current.append(block)
        current_length += len(block_text)
        if block.get("kind") == "table":
            flush()
    flush()
    return chunks[:80]


def build_work_items(blocks):
    candidates = []
    for block in blocks:
        text = block.get("text") or ""
        if not any(keyword in text for keyword in ACTION_KEYWORDS):
            continue
        action_text = _excerpt(text, limit=120)
        due_match = DATE_PATTERN.search(text)
        candidates.append(
            {
                "title": action_title(action_text),
                "action_text": action_text,
                "due_text": due_match.group("date").strip() if due_match else "",
                "target_text": target_hint(text),
                "evidence_text": _excerpt(text, limit=180),
                "confidence_score": 0.72 if due_match else 0.58,
            }
        )
        if len(candidates) >= 8:
            break
    if candidates:
        return candidates
    first_block = next((block for block in blocks if block.get("text")), None)
    if not first_block:
        return []
    text = first_block["text"]
    return [
        {
            "title": "문서 확인",
            "action_text": "원문을 보고 필요한 일을 확인합니다.",
            "due_text": "",
            "target_text": "",
            "evidence_text": _excerpt(text, limit=180),
            "confidence_score": 0.3,
        }
    ]


def find_relevant_chunks(parse_payload, question, *, limit=5):
    tokens = tokenize(question)
    chunks = list((parse_payload or {}).get("chunks") or [])
    scored = []
    for chunk in chunks:
        text = str(chunk.get("text") or chunk.get("markdown") or "")
        lowered = text.lower()
        score = sum(1 for token in tokens if token in lowered)
        if any(keyword in question for keyword in ("언제", "날짜", "기한", "마감")) and DATE_PATTERN.search(text):
            score += 2
        if chunk.get("has_evidence"):
            score += 1
        if score > 0:
            scored.append((score, len(text), chunk))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [chunk for _score, _length, chunk in scored[:limit]]


def compose_answer(question, chunks):
    evidence = _excerpt(chunks[0].get("text") or chunks[0].get("markdown") or "", limit=240)
    if any(keyword in question for keyword in ("언제", "날짜", "기한", "마감")):
        date_match = DATE_PATTERN.search(evidence)
        if date_match:
            return f"문서 기준 날짜는 {date_match.group('date').strip()}입니다. 근거: {evidence}"
    return f"문서에서 확인한 내용입니다. {evidence}"


def normalize_question(question):
    return re.sub(r"\s+", " ", str(question or "").strip()).lower()[:300]


def tokenize(value):
    return [
        token.lower()
        for token in re.findall(r"[0-9A-Za-z가-힣]+", str(value or ""))
        if len(token.strip()) >= 2
    ]


def summarize_document(markdown, *, file_name):
    for line in str(markdown or "").splitlines():
        normalized = _normalize_text(line).strip("# ")
        if normalized:
            return normalized[:120]
    return (Path(str(file_name or "문서")).stem or "문서")[:120]


def action_title(text):
    compact = _normalize_text(text)
    for keyword in ACTION_KEYWORDS:
        if keyword in compact:
            return f"{keyword} 확인"
    return compact[:40] or "확인"


def target_hint(text):
    for keyword in ("학생", "학부모", "담임", "교직원", "보호자"):
        if keyword in text:
            return keyword
    return ""


def _read_revision_bytes(revision):
    try:
        with revision.file.open("rb") as handle:
            raw_bytes = handle.read()
    except FileNotFoundError as exc:
        raise DocumentAssistantError("파일을 찾을 수 없습니다.", status_code=404) from exc
    if not raw_bytes:
        raise DocumentAssistantError("빈 파일은 정리할 수 없습니다.", status_code=400)
    if len(raw_bytes) > MAX_DOCUMENT_BYTES:
        raise DocumentAssistantError("문서가 너무 큽니다. 나눠서 올려 주세요.", status_code=400)
    return raw_bytes


def _extract_hwpx_markdown(raw_bytes):
    try:
        with zipfile.ZipFile(_bytes_io(raw_bytes), "r") as archive:
            section_files = sorted(
                name for name in archive.namelist() if name.startswith("Contents/section") and name.endswith(".xml")
            )
            if not section_files:
                raise DocumentAssistantError("HWPX 본문을 찾지 못했습니다.", status_code=400)
            blocks = []
            for section_name in section_files:
                blocks.extend(_extract_hwpx_blocks(archive.read(section_name)))
    except zipfile.BadZipFile as exc:
        raise DocumentAssistantError("HWPX 파일 형식이 올바르지 않습니다.", status_code=400) from exc
    except ET.ParseError as exc:
        raise DocumentAssistantError("HWPX XML을 읽지 못했습니다.", status_code=400) from exc

    markdown = "\n\n".join(block["markdown"] for block in blocks if block.get("markdown")).strip()
    if not markdown:
        raise DocumentAssistantError("읽을 수 있는 글을 찾지 못했습니다.", status_code=400)
    return markdown


def _bytes_io(raw_bytes):
    from io import BytesIO

    return BytesIO(raw_bytes)


def _extract_hwpx_blocks(section_xml):
    root = ET.fromstring(section_xml)
    blocks = []

    def walk(node):
        for child in list(node):
            tag_name = _local_name(child.tag)
            if tag_name == "tbl":
                table_markdown, table_text = _extract_hwpx_table(child)
                if table_markdown:
                    blocks.append({"kind": "table", "markdown": table_markdown, "text": table_text})
                continue
            if tag_name == "p":
                paragraph_text = _extract_hwpx_text(child)
                if paragraph_text:
                    blocks.append({"kind": "text", "markdown": paragraph_text, "text": paragraph_text})
                continue
            walk(child)

    walk(root)
    return blocks


def _extract_hwpx_text(node):
    parts = []
    for elem in node.iter():
        if _local_name(elem.tag) == "t":
            text = _normalize_text("".join(elem.itertext()))
            if text:
                parts.append(text)
    return " ".join(parts).strip()


def _extract_hwpx_table(node):
    rows = []
    row_texts = []
    for tr in node.iter():
        if _local_name(tr.tag) != "tr":
            continue
        row = []
        for tc in tr:
            if _local_name(tc.tag) == "tc":
                row.append(_extract_hwpx_text(tc))
        if row:
            rows.append(row)
            row_texts.append(" | ".join(cell for cell in row if cell))
    return _rows_to_markdown(rows), "\n".join(row_texts).strip()


def _rows_to_markdown(rows):
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalized = []
    for row in rows:
        cells = [_escape_cell(cell) if cell else " " for cell in row]
        cells.extend([" "] * (width - len(cells)))
        normalized.append(cells)
    lines = [
        "| " + " | ".join(normalized[0]) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    for row in normalized[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _escape_cell(text):
    return str(text or "").replace("|", r"\|").replace("\n", "<br>").strip()


def _excerpt(text, *, limit):
    normalized = _normalize_text(text)
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 1)].rstrip() + "..."


def _normalize_text(text):
    return " ".join(str(text or "").replace("\xa0", " ").split()).strip()


def _local_name(tag):
    return str(tag).rsplit("}", 1)[-1] if "}" in str(tag) else str(tag)
