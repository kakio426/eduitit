import json
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError


WORKSHEET_LAYOUT_PROFILES = ("comfortable", "compact", "tight")

MODULE_DIR = Path(__file__).resolve().parent
WORKSHEET_TEMPLATE_DIR = MODULE_DIR / "static" / "doccollab" / "worksheet"
RHWP_RUNTIME_DIR = MODULE_DIR / "vendor" / "rhwp-core-runtime"
RHWP_BUILD_SCRIPT = RHWP_RUNTIME_DIR / "build_worksheet_hwp.mjs"


class WorksheetBuildError(Exception):
    """Raised when the server-side rhwp builder cannot produce a worksheet."""


def build_worksheet_hwpx_bytes(*, content, layout_profile):
    normalized_profile = str(layout_profile or "").strip()
    if normalized_profile not in WORKSHEET_LAYOUT_PROFILES:
        raise ValidationError("지원하지 않는 학습지 레이아웃입니다.")

    template_path = WORKSHEET_TEMPLATE_DIR / f"{normalized_profile}.hwp"
    if not template_path.exists():
        raise WorksheetBuildError("학습지 템플릿을 찾지 못했습니다.")
    if not RHWP_BUILD_SCRIPT.exists():
        raise WorksheetBuildError("rhwp 서버 생성기를 찾지 못했습니다.")

    request_payload = {
        "layoutProfile": normalized_profile,
        "templatePath": str(template_path),
        "title": str(content.get("title") or "").strip(),
        "content": content,
    }

    with tempfile.TemporaryDirectory(prefix="doccollab-worksheet-") as tmpdir:
        input_path = Path(tmpdir) / "worksheet-input.json"
        output_path = Path(tmpdir) / "worksheet-output.hwpx"
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
            raise WorksheetBuildError("학습지 HWPX를 만드는 시간이 너무 오래 걸렸습니다.") from exc
        except OSError as exc:
            raise WorksheetBuildError("서버에서 rhwp 생성기를 실행하지 못했습니다.") from exc

        stdout_lines = [line.strip() for line in str(completed.stdout or "").splitlines() if line.strip()]
        stderr_text = str(completed.stderr or "").strip()
        if completed.returncode != 0:
            error_message = stderr_text or (stdout_lines[-1] if stdout_lines else "")
            raise WorksheetBuildError(error_message or "학습지 HWPX를 만들지 못했습니다.")
        if not output_path.exists():
            raise WorksheetBuildError("학습지 HWPX 파일이 만들어지지 않았습니다.")

        try:
            metadata = json.loads(stdout_lines[-1]) if stdout_lines else {}
        except json.JSONDecodeError as exc:
            raise WorksheetBuildError("학습지 HWPX 결과를 해석하지 못했습니다.") from exc

        return {
            "layout_profile": normalized_profile,
            "page_count": max(int(metadata.get("pageCount") or 0), 0),
            "file_name": str(metadata.get("fileName") or "worksheet.hwpx").strip() or "worksheet.hwpx",
            "hwpx_bytes": output_path.read_bytes(),
        }


def build_worksheet_hwp_bytes(*, content, layout_profile):
    return build_worksheet_hwpx_bytes(content=content, layout_profile=layout_profile)
