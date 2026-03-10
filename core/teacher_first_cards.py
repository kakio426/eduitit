"""Teacher-first card metadata helpers for the rebuilt home."""

from __future__ import annotations

from dataclasses import dataclass


WORKBENCH_TITLE_ALIASES = (
    ("씨앗 퀴즈", "씨앗 퀴즈"),
    ("반짝반짝", "반짝반짝"),
    ("교무수첩", "교무수첩"),
    ("학교 예약", "학교 예약"),
    ("가뿐하게 서명", "가뿐하게 서명"),
    ("교육 자료실", "교육 자료실"),
    ("수업 발표 메이커", "수업 발표 메이커"),
    ("한글문서", "한글문서 AI"),
)


@dataclass(frozen=True)
class WorkbenchCardMeta:
    title: str
    summary: str


def _clean_text(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def _short_service_title(service_label: str) -> str:
    normalized = _clean_text(service_label)
    for needle, alias in WORKBENCH_TITLE_ALIASES:
        if needle in normalized:
            return alias
    return normalized


def _build_summary(task_label: str, service_label: str, support_label: str) -> str:
    for candidate in (task_label, support_label, service_label):
        text = _clean_text(candidate)
        if not text:
            continue
        if text == _short_service_title(service_label):
            continue
        return text
    return ""


def build_workbench_card_meta(product) -> WorkbenchCardMeta:
    service_label = _clean_text(getattr(product, "title", ""))
    task_label = _clean_text(getattr(product, "teacher_first_task_label", "") or getattr(product, "solve_text", ""))
    support_label = _clean_text(
        getattr(product, "teacher_first_support_label", "")
        or getattr(product, "result_text", "")
        or getattr(product, "lead_text", "")
        or getattr(product, "description", "")
    )
    title = _short_service_title(service_label or task_label)
    summary = _build_summary(task_label, service_label, support_label)
    return WorkbenchCardMeta(title=title or service_label or "도구", summary=summary)
