import hashlib
import glob
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from pypdf import PdfReader

from products.models import Product

from .models import TextbookChunk, TextbookDocument, TextbookParseArtifact


logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 150 * 1024 * 1024
MAX_PAGE_COUNT = 600
DEFAULT_PARSER_VERSION = "opendataloader-local-v1"
MIN_SCAN_REVIEW_TOTAL_CHARS = 120
MIN_SCAN_REVIEW_CHARS_PER_PAGE = 40
TEXTUAL_NODE_TYPES = {"paragraph", "heading", "caption", "list item"}
WINDOWS_JAVA_BIN_GLOBS = (
    r"C:\Program Files\Microsoft\jdk-*\bin",
    r"C:\Program Files\Java\jdk-*\bin",
    r"C:\Program Files\Eclipse Adoptium\jdk-*\bin",
    r"C:\Program Files\OpenJDK\jdk-*\bin",
)


class ParserUnavailableError(Exception):
    pass


class ParserExecutionError(Exception):
    pass


def get_service():
    return (
        Product.objects.filter(launch_route_name="textbook_ai:main").order_by("id").first()
        or Product.objects.filter(title="PDF 분석 도우미").order_by("id").first()
    )


def _java_executable_name():
    return "java.exe" if os.name == "nt" else "java"


def _is_valid_java_bin_dir(candidate):
    if not candidate:
        return False
    bin_dir = Path(candidate)
    return bin_dir.is_dir() and (bin_dir / _java_executable_name()).exists()


def discover_java_bin_dir():
    override_dir = os.environ.get("TEXTBOOK_AI_JAVA_BIN", "").strip()
    if _is_valid_java_bin_dir(override_dir):
        return str(Path(override_dir).resolve())

    java_on_path = shutil.which("java")
    if java_on_path:
        return str(Path(java_on_path).resolve().parent)

    java_home = os.environ.get("JAVA_HOME", "").strip()
    if java_home and _is_valid_java_bin_dir(Path(java_home) / "bin"):
        return str((Path(java_home) / "bin").resolve())

    if os.name == "nt":
        for pattern in WINDOWS_JAVA_BIN_GLOBS:
            matches = sorted(glob.glob(pattern), reverse=True)
            for match in matches:
                if _is_valid_java_bin_dir(match):
                    return str(Path(match).resolve())
    return ""


def _ensure_java_runtime_on_path():
    java_bin_dir = discover_java_bin_dir()
    if not java_bin_dir:
        return ""

    current_path = os.environ.get("PATH", "")
    current_parts = [part for part in current_path.split(os.pathsep) if part]
    normalized_parts = {
        os.path.normcase(os.path.normpath(part))
        for part in current_parts
    }
    normalized_candidate = os.path.normcase(os.path.normpath(java_bin_dir))
    if normalized_candidate not in normalized_parts:
        os.environ["PATH"] = (
            f"{java_bin_dir}{os.pathsep}{current_path}"
            if current_path
            else java_bin_dir
        )
    return java_bin_dir


def get_parser_readiness():
    java_bin_dir = _ensure_java_runtime_on_path()
    java_available = bool(java_bin_dir)
    try:
        import opendataloader_pdf  # noqa: F401

        package_available = True
    except ImportError:
        package_available = False

    return {
        "is_ready": java_available and package_available,
        "java_available": java_available,
        "java_bin_dir": java_bin_dir,
        "package_available": package_available,
        "message": (
            ""
            if java_available and package_available
            else "로컬 파서를 바로 쓰려면 Java 11+ 와 `opendataloader-pdf` 설치가 필요합니다."
        ),
    }


def build_user_facing_parse_error_message(error_message):
    if isinstance(error_message, ParserUnavailableError):
        return "지금은 PDF를 읽지 못했습니다. 잠시 후 다시 시도해 주세요."
    return "PDF를 읽는 중 문제가 생겼습니다. 잠시 후 다시 시도해 주세요."


def inspect_pdf_upload(uploaded_file):
    if uploaded_file is None:
        raise ValidationError("PDF 파일을 올려 주세요.")

    content_type = str(getattr(uploaded_file, "content_type", "") or "").lower()
    filename = str(getattr(uploaded_file, "name", "") or "")
    if not filename.lower().endswith(".pdf") and "pdf" not in content_type:
        raise ValidationError("PDF 파일만 올릴 수 있습니다.")

    file_size = int(getattr(uploaded_file, "size", 0) or 0)
    if file_size <= 0:
        raise ValidationError("비어 있는 파일은 올릴 수 없습니다.")
    if file_size > MAX_FILE_BYTES:
        raise ValidationError("PDF 크기는 150MB 이하만 지원합니다.")

    uploaded_file.seek(0)
    sha256 = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        sha256.update(chunk)
    uploaded_file.seek(0)

    try:
        reader = PdfReader(uploaded_file)
        if reader.is_encrypted:
            raise ValidationError("암호가 걸린 PDF는 지원하지 않습니다.")
        page_count = len(reader.pages)
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(f"PDF를 읽지 못했습니다: {exc}") from exc
    finally:
        uploaded_file.seek(0)

    if page_count <= 0:
        raise ValidationError("페이지 수를 읽지 못한 PDF입니다.")
    if page_count > MAX_PAGE_COUNT:
        raise ValidationError("PDF는 600쪽 이하만 지원합니다.")

    return {
        "sha256": sha256.hexdigest(),
        "page_count": page_count,
        "file_size_bytes": file_size,
        "original_filename": os.path.basename(filename) or "document.pdf",
    }


def convert_pdf_with_opendataloader(pdf_path, output_dir):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    _ensure_java_runtime_on_path()

    try:
        import opendataloader_pdf

        opendataloader_pdf.convert(
            input_path=[str(pdf_path)],
            output_dir=str(output_path),
            format="json,markdown",
            reading_order="xycut",
        )
        return _read_parser_outputs(output_path)
    except ImportError:
        pass
    except Exception as exc:
        raise ParserExecutionError(f"OpenDataLoader 실행 중 오류가 발생했습니다: {exc}") from exc

    cli_cmd = os.environ.get("TEXTBOOK_AI_ODL_CMD", "opendataloader-pdf")
    command = [
        cli_cmd,
        str(pdf_path),
        "-o",
        str(output_path),
        "-f",
        "json,markdown",
        "--reading-order",
        "xycut",
        "-q",
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            timeout=int(getattr(settings, "TEXTBOOK_AI_PARSE_TIMEOUT_SECONDS", 180)),
        )
    except FileNotFoundError as exc:
        raise ParserUnavailableError(
            "OpenDataLoader PDF가 설치되지 않았습니다. `pip install -U opendataloader-pdf`와 Java 11+를 먼저 준비해 주세요."
        ) from exc
    except Exception as exc:
        raise ParserExecutionError(f"OpenDataLoader CLI 실행에 실패했습니다: {exc}") from exc

    if completed.returncode != 0:
        stderr = str(completed.stderr or completed.stdout or "").strip()
        raise ParserExecutionError(stderr or "OpenDataLoader CLI가 오류를 반환했습니다.")
    return _read_parser_outputs(output_path)


def _read_parser_outputs(output_path):
    json_files = sorted(output_path.glob("*.json"))
    markdown_files = sorted(output_path.glob("*.md"))
    if not json_files or not markdown_files:
        raise ParserExecutionError("OpenDataLoader 산출물(JSON/Markdown)을 찾지 못했습니다.")

    json_text = json_files[0].read_text(encoding="utf-8")
    markdown_text = markdown_files[0].read_text(encoding="utf-8")
    try:
        json_payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ParserExecutionError(f"파서 JSON을 해석하지 못했습니다: {exc}") from exc

    return {
        "json_payload": json_payload,
        "json_text": json_text,
        "markdown_text": markdown_text,
    }


def parse_document(document, *, force=False, parser_fn=None):
    parser_fn = parser_fn or convert_pdf_with_opendataloader
    document.parse_status = TextbookDocument.ParseStatus.PROCESSING
    document.error_message = ""
    document.parser_name = "opendataloader-pdf"
    document.parser_mode = "local"
    document.parser_version = DEFAULT_PARSER_VERSION
    document.save(
        update_fields=[
            "parse_status",
            "error_message",
            "parser_name",
            "parser_mode",
            "parser_version",
            "updated_at",
        ]
    )

    pdf_path = document.source_pdf.path
    try:
        with tempfile.TemporaryDirectory(prefix="textbook_ai_") as temp_dir:
            parsed = parser_fn(pdf_path, temp_dir)
    except (ParserUnavailableError, ParserExecutionError):
        raise
    except Exception as exc:
        raise ParserExecutionError(f"PDF 읽기 중 예기치 않은 오류가 발생했습니다: {exc}") from exc

    json_payload = dict(parsed.get("json_payload") or {})
    markdown_text = str(parsed.get("markdown_text") or "")
    normalized = normalize_opendataloader_payload(json_payload, markdown_text)
    status = (
        TextbookDocument.ParseStatus.NEEDS_REVIEW
        if normalized["needs_review"]
        else TextbookDocument.ParseStatus.READY
    )

    with transaction.atomic():
        artifact, _ = TextbookParseArtifact.objects.get_or_create(document=document)
        document.chunks.all().delete()

        artifact.parser_version = document.parser_version or DEFAULT_PARSER_VERSION
        artifact.page_count = normalized["page_count"]
        artifact.heading_count = normalized["heading_count"]
        artifact.table_count = normalized["table_count"]
        artifact.image_count = normalized["image_count"]
        artifact.text_char_count = normalized["text_char_count"]
        artifact.raw_metadata = normalized["raw_metadata"]
        artifact.summary_json = normalized["summary_json"]
        artifact.parsed_json_file.save(
            f"{document.id}.json",
            ContentFile(
                str(parsed.get("json_text") or json.dumps(json_payload, ensure_ascii=False)).encode("utf-8")
            ),
            save=False,
        )
        artifact.parsed_markdown_file.save(
            f"{document.id}.md",
            ContentFile(markdown_text.encode("utf-8")),
            save=False,
        )
        artifact.save()

        chunk_objects = [
            TextbookChunk(
                document=document,
                chunk_type=item["chunk_type"],
                heading_path=item["heading_path"],
                text=item["text"],
                search_text=item["search_text"],
                page_from=item["page_from"],
                page_to=item["page_to"],
                bbox_json=item["bbox_json"],
                metadata_json=item["metadata_json"],
                sort_order=item["sort_order"],
            )
            for item in normalized["chunks"]
        ]
        if chunk_objects:
            TextbookChunk.objects.bulk_create(chunk_objects)

        document.page_count = normalized["page_count"] or document.page_count
        document.parse_status = status
        document.error_message = ""
        document.parsed_at = timezone.now()
        document.save(
            update_fields=[
                "page_count",
                "parse_status",
                "error_message",
                "parsed_at",
                "updated_at",
            ]
        )

    return document


def mark_parse_failure(document, error_message):
    document.parse_status = TextbookDocument.ParseStatus.FAILED
    logger.warning("textbook_ai parse failure document=%s error=%s", getattr(document, "id", None), error_message)
    document.error_message = build_user_facing_parse_error_message(error_message)
    document.save(update_fields=["parse_status", "error_message", "updated_at"])
    return document


def rebuild_document_from_saved_artifact(document):
    artifact = getattr(document, "artifact", None)
    if artifact is None or not artifact.parsed_json_file:
        raise ParserExecutionError("재구성할 JSON 산출물이 없습니다.")
    artifact.parsed_json_file.open("rb")
    try:
        json_payload = json.loads(artifact.parsed_json_file.read().decode("utf-8"))
    finally:
        artifact.parsed_json_file.close()
    markdown_text = ""
    if artifact.parsed_markdown_file:
        artifact.parsed_markdown_file.open("rb")
        try:
            markdown_text = artifact.parsed_markdown_file.read().decode("utf-8")
        finally:
            artifact.parsed_markdown_file.close()

    normalized = normalize_opendataloader_payload(json_payload, markdown_text)
    with transaction.atomic():
        document.chunks.all().delete()
        chunk_objects = [
            TextbookChunk(
                document=document,
                chunk_type=item["chunk_type"],
                heading_path=item["heading_path"],
                text=item["text"],
                search_text=item["search_text"],
                page_from=item["page_from"],
                page_to=item["page_to"],
                bbox_json=item["bbox_json"],
                metadata_json=item["metadata_json"],
                sort_order=item["sort_order"],
            )
            for item in normalized["chunks"]
        ]
        if chunk_objects:
            TextbookChunk.objects.bulk_create(chunk_objects)

        artifact.page_count = normalized["page_count"]
        artifact.heading_count = normalized["heading_count"]
        artifact.table_count = normalized["table_count"]
        artifact.image_count = normalized["image_count"]
        artifact.text_char_count = normalized["text_char_count"]
        artifact.raw_metadata = normalized["raw_metadata"]
        artifact.summary_json = normalized["summary_json"]
        artifact.save(
            update_fields=[
                "page_count",
                "heading_count",
                "table_count",
                "image_count",
                "text_char_count",
                "raw_metadata",
                "summary_json",
                "updated_at",
            ]
        )
        document.page_count = normalized["page_count"] or document.page_count
        document.parse_status = (
            TextbookDocument.ParseStatus.NEEDS_REVIEW
            if normalized["needs_review"]
            else TextbookDocument.ParseStatus.READY
        )
        document.error_message = ""
        document.parsed_at = timezone.now()
        document.save(update_fields=["page_count", "parse_status", "error_message", "parsed_at", "updated_at"])

    return document


def normalize_opendataloader_payload(json_payload, markdown_text):
    root = dict(json_payload or {})
    page_count = int(root.get("number of pages") or 0)
    raw_metadata = {
        "file_name": root.get("file name") or "",
        "title": root.get("title") or "",
        "author": root.get("author") or "",
        "creation_date": root.get("creation date") or "",
        "modification_date": root.get("modification date") or "",
    }

    heading_outline = []
    table_previews = []
    segments = []
    counters = {"table_count": 0, "image_count": 0}

    def walk_children(children, heading_stack, *, inside_table=False):
        current_stack = list(heading_stack)
        for child in children or []:
            current_stack = walk_node(child, current_stack, inside_table=inside_table)
        return current_stack

    def walk_node(node, heading_stack, *, inside_table=False):
        if not isinstance(node, dict):
            return heading_stack

        current_stack = list(heading_stack)
        node_type = str(node.get("type") or "").strip().lower()
        text = clean_text(node.get("content") or "")
        page_number = safe_positive_int(node.get("page number") or 1, default=1)
        bbox = normalize_bbox(node.get("bounding box"))

        if node_type == "heading" and text:
            level = safe_positive_int(node.get("heading level") or node.get("level") or 1, default=1)
            current_stack = update_heading_stack(current_stack, level, text, page_number)
            heading_outline.append(
                {
                    "title": text,
                    "heading_level": level,
                    "page": page_number,
                    "bbox": bbox,
                }
            )
            segments.append(
                build_segment(
                    chunk_type=TextbookChunk.ChunkType.HEADING,
                    text=text,
                    page=page_number,
                    bbox=bbox,
                    heading_stack=current_stack,
                    metadata={"heading_level": level},
                )
            )
        elif node_type in TEXTUAL_NODE_TYPES and text and not inside_table:
            segments.append(
                build_segment(
                    chunk_type=TextbookChunk.ChunkType.TEXT,
                    text=text,
                    page=page_number,
                    bbox=bbox,
                    heading_stack=current_stack,
                    metadata={"node_type": node_type},
                )
            )
        elif node_type == "table":
            counters["table_count"] += 1
            table_text = flatten_node_text(node).strip()
            if table_text:
                table_previews.append({"page": page_number, "text": table_text[:320]})
                segments.append(
                    build_segment(
                        chunk_type=TextbookChunk.ChunkType.TABLE,
                        text=table_text,
                        page=page_number,
                        bbox=bbox,
                        heading_stack=current_stack,
                        metadata={"node_type": node_type},
                    )
                )
        elif node_type == "image":
            counters["image_count"] += 1

        child_inside_table = inside_table or node_type == "table"
        children = get_child_nodes(node)
        if children:
            current_stack = walk_children(children, current_stack, inside_table=child_inside_table)
        return current_stack

    walk_children(root.get("kids") or [], [])
    merged_chunks = merge_segments(segments)
    text_char_count = sum(len(chunk["text"]) for chunk in merged_chunks)

    if not page_count:
        page_count = max([chunk["page_to"] for chunk in merged_chunks], default=0)

    text_chunk_count = sum(1 for chunk in merged_chunks if chunk["chunk_type"] != TextbookChunk.ChunkType.TABLE)
    summary_json = {
        "heading_outline": heading_outline[:60],
        "table_previews": table_previews[:20],
        "content_preview_blocks": [
            {
                "chunk_type": chunk["chunk_type"],
                "heading_path": chunk["heading_path"],
                "text": chunk["text"][:280],
                "page_from": chunk["page_from"],
                "page_to": chunk["page_to"],
            }
            for chunk in merged_chunks[:12]
        ],
        "needs_review": should_mark_needs_review(
            page_count=page_count,
            text_char_count=text_char_count,
            text_chunk_count=text_chunk_count,
        ),
        "scan_review_reason": build_scan_review_reason(
            page_count=page_count,
            text_char_count=text_char_count,
            text_chunk_count=text_chunk_count,
        ),
        "markdown_char_count": len(markdown_text or ""),
        "parser_engine": "opendataloader-pdf",
        "parser_mode": "local",
    }

    return {
        "page_count": page_count,
        "heading_count": len(heading_outline),
        "table_count": counters["table_count"],
        "image_count": counters["image_count"],
        "text_char_count": text_char_count,
        "raw_metadata": raw_metadata,
        "summary_json": summary_json,
        "chunks": merged_chunks,
        "needs_review": bool(summary_json["needs_review"]),
    }


def clean_text(value):
    text = str(value or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
    return "\n".join([line for line in lines if line]).strip()


def safe_positive_int(value, *, default=0):
    try:
        resolved = int(value)
    except (TypeError, ValueError):
        return default
    return resolved if resolved > 0 else default


def normalize_bbox(value):
    if not isinstance(value, list) or len(value) != 4:
        return []
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError):
        return []


def get_child_nodes(node):
    ordered_children = []
    for key in ("kids", "list items", "rows", "cells"):
        value = node.get(key)
        if isinstance(value, list):
            ordered_children.extend([item for item in value if isinstance(item, dict)])
    if ordered_children:
        return ordered_children

    fallback_children = []
    for value in node.values():
        if isinstance(value, dict) and value.get("type"):
            fallback_children.append(value)
        elif isinstance(value, list):
            fallback_children.extend([item for item in value if isinstance(item, dict) and item.get("type")])
    return fallback_children


def update_heading_stack(stack, level, title, page_number):
    next_stack = [item for item in stack if item["level"] < level]
    next_stack.append({"level": level, "title": title, "page": page_number})
    return next_stack


def build_heading_path(heading_stack):
    return " > ".join(item["title"] for item in heading_stack if item.get("title"))


def build_segment(*, chunk_type, text, page, bbox, heading_stack, metadata):
    return {
        "chunk_type": chunk_type,
        "text": text,
        "heading_path": build_heading_path(heading_stack),
        "page_from": page,
        "page_to": page,
        "bbox_json": [{"page": page, "bbox": bbox}] if bbox else [],
        "metadata_json": dict(metadata or {}),
    }


def merge_segments(segments):
    merged = []
    for segment in segments:
        if not segment["text"]:
            continue
        if merged and can_merge_segments(merged[-1], segment):
            previous = merged[-1]
            previous["text"] = merge_text(previous["text"], segment["text"])
            previous["page_to"] = max(previous["page_to"], segment["page_to"])
            previous["bbox_json"] = [*previous.get("bbox_json", []), *segment.get("bbox_json", [])]
            previous["metadata_json"]["merged_types"] = sorted(
                set(previous["metadata_json"].get("merged_types", [previous["chunk_type"]]))
                | set(segment["metadata_json"].get("merged_types", [segment["chunk_type"]]))
            )
            if previous["chunk_type"] == TextbookChunk.ChunkType.HEADING:
                previous["chunk_type"] = segment["chunk_type"]
            continue

        candidate = dict(segment)
        candidate["metadata_json"] = dict(candidate.get("metadata_json") or {})
        candidate["metadata_json"]["merged_types"] = [candidate["chunk_type"]]
        merged.append(candidate)

    for index, chunk in enumerate(merged, start=1):
        chunk["sort_order"] = index
        chunk["search_text"] = build_search_text(chunk)
    return merged


def can_merge_segments(previous, current):
    if previous["chunk_type"] == TextbookChunk.ChunkType.TABLE or current["chunk_type"] == TextbookChunk.ChunkType.TABLE:
        return False
    if previous["page_to"] + 1 < current["page_from"]:
        return False
    if previous["heading_path"] != current["heading_path"]:
        return False
    merged_length = len(previous["text"]) + len(current["text"])
    if previous["chunk_type"] == TextbookChunk.ChunkType.HEADING:
        return merged_length <= 1200
    return merged_length <= 900 and (len(previous["text"]) < 280 or len(current["text"]) < 280)


def merge_text(first, second):
    if not first:
        return second
    if not second:
        return first
    separator = "\n\n" if not first.endswith((".", "!", "?", ":", ";")) else " "
    return f"{first}{separator}{second}".strip()


def flatten_node_text(node):
    parts = []

    def _walk(value):
        if isinstance(value, dict):
            node_type = str(value.get("type") or "").strip().lower()
            content = clean_text(value.get("content") or "")
            if content and node_type in TEXTUAL_NODE_TYPES:
                parts.append(content)
            for child in get_child_nodes(value):
                _walk(child)
        elif isinstance(value, list):
            for item in value:
                _walk(item)

    _walk(node)
    return " ".join(part for part in parts if part).strip()


def should_mark_needs_review(*, page_count, text_char_count, text_chunk_count):
    if page_count <= 0:
        return True
    if text_char_count < MIN_SCAN_REVIEW_TOTAL_CHARS:
        return True
    if text_chunk_count <= 0:
        return True
    return (text_char_count / max(page_count, 1)) < MIN_SCAN_REVIEW_CHARS_PER_PAGE


def build_scan_review_reason(*, page_count, text_char_count, text_chunk_count):
    if not should_mark_needs_review(
        page_count=page_count,
        text_char_count=text_char_count,
        text_chunk_count=text_chunk_count,
    ):
        return ""
    return "텍스트 추출량이 낮아 스캔본이거나 복잡한 PDF일 수 있습니다. OCR/hybrid 지원 전에는 결과를 직접 확인해 주세요."


def build_search_text(chunk):
    values = [
        chunk.get("heading_path", ""),
        chunk.get("text", ""),
        str(chunk.get("page_from") or ""),
        str(chunk.get("page_to") or ""),
    ]
    return " ".join(value for value in values if value).strip()


def tokenize_search_query(query):
    return [token.lower() for token in re.findall(r"[0-9A-Za-z가-힣]+", str(query or "")) if token.strip()]


def search_document_chunks(document, query):
    tokens = tokenize_search_query(query)
    if not tokens:
        return []

    chunk_queryset = TextbookChunk.objects.filter(document=document)
    filters = Q()
    for token in tokens[:6]:
        filters |= Q(search_text__icontains=token)
    candidates = list(chunk_queryset.filter(filters).order_by("page_from", "sort_order")[:120])
    scored = []
    lowered_query = str(query or "").strip().lower()

    for chunk in candidates:
        haystack = str(chunk.search_text or chunk.text or "").lower()
        token_score = sum(1 for token in tokens if token in haystack)
        exact_bonus = 2 if lowered_query and lowered_query in haystack else 0
        if token_score <= 0 and exact_bonus <= 0:
            continue
        scored.append(
            {
                "chunk": chunk,
                "score": token_score + exact_bonus,
                "snippet": build_snippet(chunk.text, tokens),
                "source_label": build_source_label(chunk),
            }
        )

    return sorted(
        scored,
        key=lambda item: (-item["score"], item["chunk"].page_from, item["chunk"].sort_order),
    )[:12]


def build_snippet(text, tokens):
    value = clean_text(text)
    if not value:
        return ""
    lowered = value.lower()
    for token in tokens:
        index = lowered.find(token.lower())
        if index >= 0:
            start = max(index - 80, 0)
            end = min(index + 160, len(value))
            prefix = "..." if start > 0 else ""
            suffix = "..." if end < len(value) else ""
            return f"{prefix}{value[start:end]}{suffix}"
    return value[:220] + ("..." if len(value) > 220 else "")


def build_source_label(chunk):
    if chunk.page_from == chunk.page_to:
        return f"{chunk.page_from}쪽"
    return f"{chunk.page_from}-{chunk.page_to}쪽"
