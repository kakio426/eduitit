import io
import os
import zipfile
import xml.etree.ElementTree as ET


class HwpxParseError(Exception):
    """Raised when HWPX parsing fails."""


def parse_hwpx_to_markdown(uploaded_file):
    parsed = parse_hwpx_document(uploaded_file)
    return parsed["markdown_text"]


def parse_hwpx_document(uploaded_file=None, *, raw_bytes=None, file_name=""):
    if uploaded_file is None and raw_bytes is None:
        raise HwpxParseError("No file was provided.")

    resolved_name = (file_name or getattr(uploaded_file, "name", "") or "").strip()
    file_name_lower = resolved_name.lower()
    if not file_name_lower.endswith(".hwpx"):
        raise HwpxParseError("Only .hwpx files are supported.")

    if raw_bytes is None:
        raw_bytes = _read_uploaded_file_bytes(uploaded_file)
    if not raw_bytes:
        raise HwpxParseError("Uploaded file is empty.")

    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes), "r") as archive:
            section_files = sorted(
                name
                for name in archive.namelist()
                if name.startswith("Contents/section") and name.endswith(".xml")
            )
            if not section_files:
                raise HwpxParseError("No section XML files found in HWPX.")

            blocks = []
            for section_name in section_files:
                section_xml = archive.read(section_name)
                blocks.extend(_extract_blocks_from_section(section_xml, section_name=section_name))
    except zipfile.BadZipFile as exc:
        raise HwpxParseError("Invalid HWPX zip structure.") from exc
    except ET.ParseError as exc:
        raise HwpxParseError("Invalid XML inside HWPX.") from exc
    except HwpxParseError:
        raise
    except Exception as exc:
        raise HwpxParseError("Unexpected error while parsing HWPX.") from exc

    markdown_blocks = [block["markdown"] for block in blocks if (block.get("markdown") or "").strip()]
    markdown_text = "\n\n".join(markdown_blocks).strip()
    if not markdown_text:
        raise HwpxParseError("No readable text or table content found.")

    first_text_block = next(
        (block.get("text", "") for block in blocks if block.get("kind") == "text" and block.get("text")),
        "",
    )
    document_title = _build_document_title(resolved_name, first_text_block)
    chunks = _build_chunks(blocks)

    return {
        "markdown_text": markdown_text,
        "document_title": document_title,
        "char_count": len(markdown_text),
        "first_text_block": first_text_block,
        "blocks": blocks,
        "chunks": chunks,
    }


def _build_document_title(file_name, first_text_block):
    candidate = _normalize_text(first_text_block)
    if candidate:
        return candidate[:120]
    stem = os.path.splitext(os.path.basename(file_name or "문서.hwpx"))[0]
    return (stem or "문서")[:120]


def _read_uploaded_file_bytes(uploaded_file):
    try:
        uploaded_file.seek(0)
    except Exception:
        pass

    try:
        raw_bytes = uploaded_file.read()
    except Exception as exc:
        raise HwpxParseError("Failed to read uploaded file in memory.") from exc
    finally:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass

    if not raw_bytes:
        raise HwpxParseError("Uploaded file is empty.")
    return raw_bytes


def _extract_blocks_from_section(section_xml_bytes, *, section_name):
    root = ET.fromstring(section_xml_bytes)
    blocks = []
    block_order = 0

    def walk(node):
        nonlocal block_order
        for child in list(node):
            tag_name = _local_name(child.tag)

            if tag_name == "tbl":
                table_markdown, table_text = _extract_markdown_table(child)
                if table_markdown:
                    block_order += 1
                    blocks.append(
                        {
                            "id": f"{section_name}:{block_order}",
                            "kind": "table",
                            "section_label": section_name,
                            "order": block_order,
                            "text": table_text,
                            "markdown": table_markdown,
                        }
                    )
                continue

            if tag_name == "p":
                paragraph_text = _extract_paragraph_text(child)
                if paragraph_text:
                    block_order += 1
                    blocks.append(
                        {
                            "id": f"{section_name}:{block_order}",
                            "kind": "text",
                            "section_label": section_name,
                            "order": block_order,
                            "text": paragraph_text,
                            "markdown": paragraph_text,
                        }
                    )
                continue

            walk(child)

    walk(root)
    return blocks


def _extract_paragraph_text(paragraph_element):
    text_parts = []
    for elem in paragraph_element.iter():
        if _local_name(elem.tag) == "t":
            text = _normalize_text("".join(elem.itertext()))
            if text:
                text_parts.append(text)
    return " ".join(text_parts).strip()


def _extract_markdown_table(tbl_element):
    rows = []
    row_texts = []
    for tr in tbl_element.iter():
        if _local_name(tr.tag) != "tr":
            continue

        row = []
        for tc in tr:
            if _local_name(tc.tag) != "tc":
                continue
            cell_text = _extract_cell_text(tc)
            row.append(cell_text)

        if row:
            rows.append(row)
            row_texts.append(" | ".join(value for value in row if value))

    return _rows_to_markdown_table(rows), "\n".join(row_texts).strip()


def _extract_cell_text(tc_element):
    text_parts = []
    for elem in tc_element.iter():
        if _local_name(elem.tag) == "t":
            text = _normalize_text("".join(elem.itertext()))
            if text:
                text_parts.append(text)
    return " ".join(text_parts).strip()


def _rows_to_markdown_table(rows):
    if not rows:
        return ""

    max_columns = max((len(row) for row in rows), default=0)
    if max_columns <= 0:
        return ""

    normalized_rows = []
    for row in rows:
        normalized = [(_escape_markdown_cell(cell) if cell else " ") for cell in row]
        while len(normalized) < max_columns:
            normalized.append(" ")
        normalized_rows.append(normalized)

    header = normalized_rows[0]
    separator = ["---"] * max_columns
    body_rows = normalized_rows[1:]

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    for row in body_rows:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def _build_chunks(blocks, *, max_chars=1200):
    chunks = []
    current_blocks = []
    current_length = 0

    def flush():
        nonlocal current_blocks, current_length
        if not current_blocks:
            return
        chunk_index = len(chunks) + 1
        chunks.append(
            {
                "id": f"chunk-{chunk_index}",
                "section_label": current_blocks[0].get("section_label") or "section",
                "text": "\n\n".join(block.get("text", "") for block in current_blocks if block.get("text")).strip(),
                "markdown": "\n\n".join(block.get("markdown", "") for block in current_blocks if block.get("markdown")).strip(),
                "block_ids": [block.get("id") for block in current_blocks if block.get("id")],
                "has_evidence": any(block.get("kind") == "table" for block in current_blocks),
            }
        )
        current_blocks = []
        current_length = 0

    for block in blocks:
        block_text = block.get("text") or block.get("markdown") or ""
        if not block_text:
            continue
        projected_length = current_length + len(block_text)
        if current_blocks and projected_length > max_chars:
            flush()
        current_blocks.append(block)
        current_length += len(block_text)
        if block.get("kind") == "table" and current_blocks:
            flush()
    flush()
    return chunks


def _escape_markdown_cell(text):
    return text.replace("|", r"\|").replace("\n", "<br>").strip()


def _normalize_text(text):
    if not text:
        return ""
    return " ".join(text.replace("\xa0", " ").split()).strip()


def _local_name(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag
