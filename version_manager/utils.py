import difflib
from pathlib import Path

from PyPDF2 import PdfReader
from docx import Document as DocxDocument


def extract_text_from_uploaded(upload_field):
    if not upload_field:
        return None, '파일이 없습니다.'

    ext = Path(upload_field.name).suffix.lower()
    try:
        with upload_field.open('rb') as handle:
            if ext in {'.txt', '.md', '.csv', '.log'}:
                raw = handle.read()
                for encoding in ('utf-8', 'cp949', 'euc-kr'):
                    try:
                        return raw.decode(encoding), 'ok'
                    except UnicodeDecodeError:
                        continue
                return None, '텍스트 인코딩을 해석하지 못했습니다.'

            if ext == '.docx':
                doc = DocxDocument(handle)
                lines = [paragraph.text for paragraph in doc.paragraphs if paragraph.text]
                return '\n'.join(lines), 'ok'

            if ext == '.pdf':
                reader = PdfReader(handle)
                pages = [(page.extract_text() or '') for page in reader.pages]
                return '\n'.join(pages), 'ok'
    except Exception as exc:
        return None, f'텍스트 추출 중 오류: {exc}'

    return None, f'{ext or "해당 형식"}은 diff를 지원하지 않습니다.'


def make_diff_summary(previous_text, current_text, max_lines=60):
    if previous_text is None or current_text is None:
        return '', False
    if previous_text == current_text:
        return '변경 내용이 감지되지 않았습니다.', True

    diff_lines = list(
        difflib.unified_diff(
            previous_text.splitlines(),
            current_text.splitlines(),
            fromfile='previous',
            tofile='current',
            lineterm='',
            n=2,
        )
    )
    if len(diff_lines) > max_lines:
        diff_lines = diff_lines[:max_lines] + ['... (이하 생략)']
    return '\n'.join(diff_lines), True

