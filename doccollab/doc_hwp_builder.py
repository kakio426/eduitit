import json
import re
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape

from django.conf import settings

from .document_spec import TABLE_BLOCK_TYPES, normalize_document_spec, validate_document_spec


MODULE_DIR = Path(__file__).resolve().parent
DOCUMENT_TEMPLATE_PATH = MODULE_DIR / "static" / "doccollab" / "worksheet" / "comfortable.hwp"
RHWP_RUNTIME_DIR = MODULE_DIR / "vendor" / "rhwp-core-runtime"
RHWP_BUILD_SCRIPT = RHWP_RUNTIME_DIR / "build_document_hwp.mjs"


class DocumentBuildError(Exception):
    """Raised when the server-side rhwp builder cannot produce a document."""


def build_document_hwpx_bytes(*, content):
    if not isinstance(content, dict):
        raise DocumentBuildError("문서 내용을 해석하지 못했습니다.")
    content = normalize_document_spec(
        content,
        document_type=content.get("document_type") or "freeform",
        prompt=content.get("summary_text") or content.get("title") or "학교 실무 문서 초안",
        selected_blocks=content.get("selected_blocks"),
    )
    issues = validate_document_spec(content)
    if issues:
        raise DocumentBuildError(issues[0])
    if not DOCUMENT_TEMPLATE_PATH.exists():
        raise DocumentBuildError("문서 템플릿을 찾지 못했습니다.")
    if not RHWP_BUILD_SCRIPT.exists():
        raise DocumentBuildError("rhwp 서버 생성기를 찾지 못했습니다.")

    title = str(content.get("title") or "").strip() or "문서 초안"
    request_payload = {
        "templatePath": str(DOCUMENT_TEMPLATE_PATH),
        "title": title,
        "content": content,
    }

    with tempfile.TemporaryDirectory(prefix="doccollab-document-") as tmpdir:
        input_path = Path(tmpdir) / "document-input.json"
        output_path = Path(tmpdir) / "document-output.hwpx"
        input_path.write_text(json.dumps(request_payload, ensure_ascii=False), encoding="utf-8")

        try:
            completed = subprocess.run(
                [
                    str(getattr(settings, "NODE_BINARY", "node") or "node"),
                    str(RHWP_BUILD_SCRIPT),
                    str(input_path),
                    str(output_path),
                ],
                cwd=str(RHWP_RUNTIME_DIR),
                capture_output=True,
                text=True,
                timeout=90,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise DocumentBuildError("문서 HWPX를 만드는 시간이 너무 오래 걸렸습니다.") from exc
        except OSError as exc:
            raise DocumentBuildError("서버에서 rhwp 생성기를 실행하지 못했습니다.") from exc

        stdout_lines = [line.strip() for line in str(completed.stdout or "").splitlines() if line.strip()]
        stderr_text = str(completed.stderr or "").strip()
        if completed.returncode != 0:
            error_message = stderr_text or (stdout_lines[-1] if stdout_lines else "")
            raise DocumentBuildError(error_message or "문서 HWPX를 만들지 못했습니다.")
        if not output_path.exists():
            raise DocumentBuildError("문서 HWPX 파일이 만들어지지 않았습니다.")

        try:
            metadata = json.loads(stdout_lines[-1]) if stdout_lines else {}
        except json.JSONDecodeError as exc:
            raise DocumentBuildError("문서 HWPX 결과를 해석하지 못했습니다.") from exc

        page_count = max(int(metadata.get("pageCount") or 0), 0)
        issues = validate_document_spec(content, page_count=page_count)
        if issues:
            raise DocumentBuildError(issues[0])

        hwpx_bytes = output_path.read_bytes()
        hwpx_bytes = inject_document_spec_tables(hwpx_bytes=hwpx_bytes, content=content)

        return {
            "page_count": page_count,
            "file_name": str(metadata.get("fileName") or document_hwpx_file_name(title)).strip() or document_hwpx_file_name(title),
            "hwpx_bytes": hwpx_bytes,
        }


def build_document_hwp_bytes(*, content):
    return build_document_hwpx_bytes(content=content)


def document_hwpx_file_name(title):
    stem = re.sub(r"[\s]+", " ", str(title or "").strip()).strip()
    stem = re.sub(r'[\\/:*?"<>|]+', " ", stem).strip()[:80] or "document"
    return f"{stem}.hwpx"


def document_hwp_file_name(title):
    return document_hwpx_file_name(title)


def inject_document_spec_tables(*, hwpx_bytes, content):
    if content.get("schema_version") != "document-spec-v2":
        return hwpx_bytes
    table_blocks = [
        block
        for block in content.get("blocks") or []
        if isinstance(block, dict) and block.get("type") in TABLE_BLOCK_TYPES
    ][:4]
    if not table_blocks:
        return hwpx_bytes

    source = BytesIO(hwpx_bytes)
    target = BytesIO()
    with ZipFile(source, "r") as archive, ZipFile(target, "w", ZIP_DEFLATED) as rewritten:
        for info in archive.infolist():
            data = archive.read(info.filename)
            if info.filename == "Contents/header.xml":
                data = _ensure_table_border_fill(data.decode("utf-8", errors="ignore")).encode("utf-8")
            elif info.filename == "Contents/section0.xml":
                data = _inject_tables_into_section(data.decode("utf-8", errors="ignore"), table_blocks).encode("utf-8")
            rewritten.writestr(info, data)
    return target.getvalue()


def _ensure_table_border_fill(header_xml):
    if '<hh:borderFill id="5"' in header_xml:
        return header_xml
    header_fill = (
        '<hh:borderFill id="5" threeD="0" shadow="0" centerLine="NONE" breakCellSeparateLine="0">'
        '<hh:slash type="NONE" Crooked="0" isCounter="0"/>'
        '<hh:backSlash type="NONE" Crooked="0" isCounter="0"/>'
        '<hh:leftBorder type="SOLID" width="0.12 mm" color="#808080"/>'
        '<hh:rightBorder type="SOLID" width="0.12 mm" color="#808080"/>'
        '<hh:topBorder type="SOLID" width="0.12 mm" color="#808080"/>'
        '<hh:bottomBorder type="SOLID" width="0.12 mm" color="#808080"/>'
        '<hh:diagonal type="NONE" width="0.1 mm" color="#808080"/>'
        '<hc:fillBrush><hc:winBrush faceColor="#EDEDED" hatchColor="#FF000000" alpha="0"/></hc:fillBrush>'
        '</hh:borderFill>'
    )
    header_xml = re.sub(
        r'(<hh:borderFills itemCnt=")(\d+)(">)',
        lambda match: f'{match.group(1)}{max(int(match.group(2)), 4) + 1}{match.group(3)}',
        header_xml,
        count=1,
    )
    return header_xml.replace("</hh:borderFills>", f"{header_fill}</hh:borderFills>", 1)


def _inject_tables_into_section(section_xml, table_blocks):
    paragraph_ends = [match.end() for match in re.finditer(r"</hp:p>", section_xml)]
    if not paragraph_ends:
        return section_xml
    anchors = [3, 5, 6, 7]
    insertions = []
    for index, block in enumerate(table_blocks):
        anchor_index = min(anchors[index], len(paragraph_ends) - 1)
        insertions.append((paragraph_ends[anchor_index], _table_block_to_hwpx_xml(block, table_index=index)))
    for offset, fragment in sorted(insertions, reverse=True):
        section_xml = section_xml[:offset] + fragment + section_xml[offset:]
    return section_xml


def _table_block_to_hwpx_xml(block, *, table_index):
    headers = [str(item or "").strip()[:30] for item in block.get("headers") or []]
    headers = [item for item in headers if item][:5]
    if not headers:
        headers = ["항목", "내용"]
    rows = []
    for row in block.get("rows") or []:
        cells = [str(item or "").strip()[:110] or "확인 필요" for item in list(row)[: len(headers)]]
        while len(cells) < len(headers):
            cells.append("확인 필요")
        rows.append(cells)
        if len(rows) >= 8:
            break
    if not rows:
        rows = [["확인 필요" for _ in headers]]

    all_rows = [headers] + rows
    col_count = len(headers)
    row_count = len(all_rows)
    col_width = max(48000 // col_count, 6500)
    table_width = col_width * col_count
    row_height = 1850
    table_height = row_height * row_count
    table_id = 810000000 + table_index
    table_xml = [
        (
            f'<hp:p id="2147483648" paraPrIDRef="33" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="10">'
            f'<hp:tbl id="{table_id}" zOrder="{table_index + 1}" numberingType="TABLE" textWrap="TOP_AND_BOTTOM" '
            f'textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" pageBreak="CELL" repeatHeader="1" '
            f'rowCnt="{row_count}" colCnt="{col_count}" cellSpacing="0" borderFillIDRef="3" noAdjust="0">'
            f'<hp:sz width="{table_width}" widthRelTo="ABSOLUTE" height="{table_height}" heightRelTo="ABSOLUTE" protect="0"/>'
            f'<hp:pos treatAsChar="0" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" '
            f'vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
            f'<hp:outMargin left="0" right="0" top="180" bottom="260"/>'
            f'<hp:inMargin left="141" right="141" top="141" bottom="141"/>'
        )
    ]
    for row_index, row in enumerate(all_rows):
        table_xml.append("<hp:tr>")
        for col_index, cell in enumerate(row):
            table_xml.append(
                _table_cell_xml(
                    cell,
                    row_index=row_index,
                    col_index=col_index,
                    width=col_width,
                    height=row_height,
                    is_header=row_index == 0,
                )
            )
        table_xml.append("</hp:tr>")
    table_xml.append(
        '</hp:tbl><hp:t/></hp:run>'
        '<hp:linesegarray><hp:lineseg textpos="0" vertpos="0" vertsize="1850" textheight="1850" '
        'baseline="1572" spacing="500" horzpos="0" horzsize="48190" flags="393216"/></hp:linesegarray></hp:p>'
    )
    return "".join(table_xml)


def _table_cell_xml(text, *, row_index, col_index, width, height, is_header):
    safe_text = escape(str(text or "").strip() or "확인 필요")
    border_fill_id = "5" if is_header else "3"
    char_pr_id = "11" if is_header else "10"
    return (
        f'<hp:tc name="" header="{1 if is_header else 0}" hasMargin="0" protect="0" editable="0" dirty="0" borderFillIDRef="{border_fill_id}">'
        f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="CENTER" '
        f'linkListIDRef="0" linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
        f'<hp:p id="2147483648" paraPrIDRef="33" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
        f'<hp:run charPrIDRef="{char_pr_id}"><hp:t>{safe_text}</hp:t></hp:run>'
        f'<hp:linesegarray><hp:lineseg textpos="0" vertpos="0" vertsize="950" textheight="950" baseline="807" '
        f'spacing="430" horzpos="0" horzsize="{max(width - 282, 1000)}" flags="393216"/></hp:linesegarray>'
        f'</hp:p></hp:subList>'
        f'<hp:cellAddr colAddr="{col_index}" rowAddr="{row_index}"/>'
        f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
        f'<hp:cellSz width="{width}" height="{height}"/>'
        f'<hp:cellMargin left="141" right="141" top="141" bottom="141"/>'
        f'</hp:tc>'
    )
