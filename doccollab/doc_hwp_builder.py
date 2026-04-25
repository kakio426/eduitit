import json
import re
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings


MODULE_DIR = Path(__file__).resolve().parent
DOCUMENT_TEMPLATE_PATH = MODULE_DIR / "static" / "doccollab" / "worksheet" / "comfortable.hwp"
RHWP_RUNTIME_DIR = MODULE_DIR / "vendor" / "rhwp-core-runtime"
RHWP_BUILD_SCRIPT = RHWP_RUNTIME_DIR / "build_document_hwp.mjs"


class DocumentBuildError(Exception):
    """Raised when the server-side rhwp builder cannot produce a document."""


def build_document_hwpx_bytes(*, content):
    if not isinstance(content, dict):
        raise DocumentBuildError("문서 내용을 해석하지 못했습니다.")
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

        return {
            "page_count": max(int(metadata.get("pageCount") or 0), 0),
            "file_name": str(metadata.get("fileName") or document_hwpx_file_name(title)).strip() or document_hwpx_file_name(title),
            "hwpx_bytes": output_path.read_bytes(),
        }


def build_document_hwp_bytes(*, content):
    return build_document_hwpx_bytes(content=content)


def document_hwpx_file_name(title):
    stem = re.sub(r"[\s]+", " ", str(title or "").strip()).strip()
    stem = re.sub(r'[\\/:*?"<>|]+', " ", stem).strip()[:80] or "document"
    return f"{stem}.hwpx"


def document_hwp_file_name(title):
    return document_hwpx_file_name(title)
