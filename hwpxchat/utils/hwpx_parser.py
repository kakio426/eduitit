import io
import zipfile
import xml.etree.ElementTree as ET


class HwpxParseError(Exception):
    """Raised when HWPX parsing fails."""


def parse_hwpx_to_markdown(uploaded_file):
    """
    Parse an uploaded HWPX file in-memory and convert key content to Markdown.

    - Text blocks: hp:t
    - Tables: hp:tbl -> Markdown table format
    """
    if not uploaded_file:
        raise HwpxParseError("No file was provided.")

    file_name = (getattr(uploaded_file, "name", "") or "").lower()
    if not file_name.endswith(".hwpx"):
        raise HwpxParseError("Only .hwpx files are supported.")

    raw_bytes = _read_uploaded_file_bytes(uploaded_file)

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
                blocks.extend(_extract_blocks_from_section(section_xml))
    except zipfile.BadZipFile as exc:
        raise HwpxParseError("Invalid HWPX zip structure.") from exc
    except ET.ParseError as exc:
        raise HwpxParseError("Invalid XML inside HWPX.") from exc
    except HwpxParseError:
        raise
    except Exception as exc:
        raise HwpxParseError("Unexpected error while parsing HWPX.") from exc

    markdown_text = "\n\n".join(block for block in blocks if block.strip()).strip()
    if not markdown_text:
        raise HwpxParseError("No readable text or table content found.")
    return markdown_text


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


def _extract_blocks_from_section(section_xml_bytes):
    root = ET.fromstring(section_xml_bytes)
    blocks = []

    def walk(node):
        for child in list(node):
            tag_name = _local_name(child.tag)

            if tag_name == "tbl":
                table_markdown = _extract_markdown_table(child)
                if table_markdown:
                    blocks.append(table_markdown)
                continue

            if tag_name == "t":
                text = _normalize_text("".join(child.itertext()))
                if text:
                    blocks.append(text)
                continue

            walk(child)

    walk(root)
    return blocks


def _extract_markdown_table(tbl_element):
    rows = []
    for tr in tbl_element.iter():
        if _local_name(tr.tag) != "tr":
            continue

        row = []
        for tc in tr:
            if _local_name(tc.tag) != "tc":
                continue
            row.append(_extract_cell_text(tc))

        if row:
            rows.append(row)

    return _rows_to_markdown_table(rows)


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


def _escape_markdown_cell(text):
    return text.replace("|", r"\|").replace("\n", "<br>").strip()


def _normalize_text(text):
    if not text:
        return ""
    return " ".join(text.replace("\xa0", " ").split()).strip()


def _local_name(tag):
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag

