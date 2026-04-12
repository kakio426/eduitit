"""Teacher-first card metadata helpers for the rebuilt home."""

from __future__ import annotations

from dataclasses import dataclass

from .service_launcher import get_public_product_name, sanitize_public_display_text


WORKBENCH_TITLE_ALIASES = (
    ("씨앗 퀴즈", "씨앗 퀴즈"),
    ("반짝반짝", "반짝반짝"),
    ("학교 예약", "학교 예약"),
    ("가뿐하게 서명", "가뿐하게 서명"),
    ("교육 자료실", "교육 자료실"),
    ("수업 발표 메이커", "수업 발표 메이커"),
    ("한글문서", "한글문서 AI"),
    ("업무 메시지", "메시지 보관"),
)

FAVORITE_TITLE_ALIASES = (
    ("씨앗 퀴즈", "씨앗 퀴즈"),
    ("반짝반짝", "알림판"),
    ("가뿐하게 서명", "서명"),
    ("교실 체스", "체스"),
    ("교실 장기", "장기"),
    ("교실 윷놀이", "윷놀이"),
    ("글솜씨 뚝딱", "소식지"),
    ("선생님 사주", "사주"),
    ("선생님 운세", "운세"),
    ("미술 수업", "미술 수업"),
    ("학교 예약", "학교 예약"),
    ("교육 자료실", "교육 자료실"),
    ("수업 발표 메이커", "수업 발표 메이커"),
    ("한글문서", "한글문서 AI"),
    ("업무 메시지", "메시지 보관"),
)


@dataclass(frozen=True)
class WorkbenchCardMeta:
    title: str
    summary: str


def _clean_text(value: str | None) -> str:
    return sanitize_public_display_text(value)


def _build_compact_service_title(service_label: str, aliases: tuple[tuple[str, str], ...]) -> str:
    normalized = _clean_text(service_label)
    for needle, alias in aliases:
        if needle in normalized:
            return alias
    return normalized


def build_workbench_service_title(service_label: str) -> str:
    return _build_compact_service_title(service_label, WORKBENCH_TITLE_ALIASES)


def build_favorite_service_title(service_label: str) -> str:
    return _build_compact_service_title(service_label, FAVORITE_TITLE_ALIASES)


def _build_summary(task_label: str, service_label: str, support_label: str) -> str:
    for candidate in (task_label, support_label, service_label):
        text = _clean_text(candidate)
        if not text:
            continue
        if text == build_workbench_service_title(service_label):
            continue
        return text
    return ""


def build_workbench_card_meta(product) -> WorkbenchCardMeta:
    service_label = _clean_text(get_public_product_name(product) or getattr(product, "title", ""))
    task_label = _clean_text(getattr(product, "teacher_first_task_label", "") or getattr(product, "solve_text", ""))
    support_label = _clean_text(
        getattr(product, "teacher_first_support_label", "")
        or getattr(product, "result_text", "")
        or getattr(product, "lead_text", "")
        or getattr(product, "description", "")
    )
    title = build_workbench_service_title(service_label or task_label)
    summary = _build_summary(task_label, service_label, support_label)
    return WorkbenchCardMeta(title=title or service_label or "도구", summary=summary)
