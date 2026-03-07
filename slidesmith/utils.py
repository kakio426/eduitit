from __future__ import annotations

from dataclasses import dataclass


DEFAULT_DECK_TITLE = "학부모 설명회 자료"
DEFAULT_DECK_TEXT = """학급 운영 방향
- 아이들이 하루 흐름을 예측할 수 있게 루틴을 고정합니다.
- 수업과 놀이가 균형 있게 이어지도록 시간을 설계합니다.
- 가정과 학교의 소통 내용을 짧고 분명하게 공유합니다.
---
준비물과 약속
- 개인 물통과 실내화를 매일 확인합니다.
- 결석 연락은 오전 8시 40분 전까지 부탁드립니다.
- 알림장과 주간 안내를 함께 확인해 주세요.
---
질문과 마무리
- 발표 후에 질문을 차례대로 받겠습니다.
- 오늘 안내 자료는 다시 열어서 바로 보여드릴 수 있습니다.
"""


@dataclass(frozen=True)
class Slide:
    title: str
    bullets: list[str]
    paragraphs: list[str]
    slide_number: int
    kind: str = "content"


def normalize_deck_title(raw_title: str | None) -> str:
    title = (raw_title or "").strip()
    return title or DEFAULT_DECK_TITLE


def normalize_deck_text(raw_text: str | None) -> str:
    text = (raw_text or "").strip()
    return text or DEFAULT_DECK_TEXT


def build_slide_deck(raw_title: str | None, raw_text: str | None) -> dict[str, object]:
    title = normalize_deck_title(raw_title)
    text = normalize_deck_text(raw_text)
    slides = [_build_cover_slide(title)]

    for index, block in enumerate(_split_blocks(text), start=2):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue

        slide_title = lines[0]
        bullets: list[str] = []
        paragraphs: list[str] = []
        for line in lines[1:]:
            if line.startswith(("- ", "* ")):
                bullets.append(line[2:].strip())
            else:
                paragraphs.append(line)

        if not bullets and not paragraphs:
            paragraphs.append("핵심 내용을 한 줄씩 덧붙여 주세요.")

        slides.append(
            Slide(
                title=slide_title,
                bullets=bullets,
                paragraphs=paragraphs,
                slide_number=index,
            )
        )

    content_slide_count = max(len(slides) - 1, 0)
    estimated_minutes = max(content_slide_count, 3)
    return {
        "title": title,
        "text": text,
        "slides": slides,
        "slide_count": len(slides),
        "content_slide_count": content_slide_count,
        "estimated_minutes": estimated_minutes,
    }


def _build_cover_slide(title: str) -> Slide:
    return Slide(
        title=title,
        bullets=["교사 설명 흐름에 맞춰 바로 발표할 수 있는 표지 슬라이드입니다."],
        paragraphs=["왼쪽 편집 화면에서 내용을 바꾸면 새 탭 발표 화면으로 바로 이어집니다."],
        slide_number=1,
        kind="cover",
    )


def _split_blocks(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n")
    return [block.strip() for block in normalized.split("\n---\n") if block.strip()]
