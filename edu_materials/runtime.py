import base64
from functools import lru_cache
from pathlib import Path
import re


_HEAD_TAG_RE = re.compile(r"(?is)<head\b[^>]*>")
_BODY_TAG_RE = re.compile(r"(?is)<body\b[^>]*>")
_DOCTYPE_RE = re.compile(r"(?is)^\s*<!DOCTYPE[^>]*>\s*")
_RUNTIME_GUARD_SENTINEL = "edu-materials-runtime-guard"
_RUNTIME_GUARD_PATH = (
    Path(__file__).resolve().parent
    / "static"
    / "edu_materials"
    / "material_runtime_guard.js"
)


@lru_cache(maxsize=1)
def _load_runtime_guard_script() -> str:
    return _RUNTIME_GUARD_PATH.read_text(encoding="utf-8").strip()


def build_runtime_html(html_content: str) -> str:
    html = str(html_content or "")
    if not html.strip() or _RUNTIME_GUARD_SENTINEL in html:
        return html

    bundle = (
        f"<!-- {_RUNTIME_GUARD_SENTINEL} -->\n"
        f"<script>{_load_runtime_guard_script()}</script>\n"
    )

    head_match = _HEAD_TAG_RE.search(html)
    if head_match:
        return html[: head_match.end()] + "\n" + bundle + html[head_match.end() :]

    body_match = _BODY_TAG_RE.search(html)
    if body_match:
        return html[: body_match.end()] + "\n" + bundle + html[body_match.end() :]

    doctype_match = _DOCTYPE_RE.match(html)
    if doctype_match:
        return html[: doctype_match.end()] + bundle + html[doctype_match.end() :]

    return bundle + html


def build_runtime_data_url(html_content: str) -> str:
    runtime_html = build_runtime_html(html_content)
    encoded = base64.b64encode(runtime_html.encode("utf-8")).decode("ascii")
    return f"data:text/html;charset=utf-8;base64,{encoded}"
