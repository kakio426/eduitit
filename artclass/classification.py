import re
from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class AutoMetadata:
    category: str
    grade_band: str
    tags: list[str]
    confidence: float
    search_text: str
    suggested_title: str


CATEGORY_RULES = [
    ("감상", ("감상", "미술사", "명화", "작가", "작품 읽기", "전시", "박물관")),
    ("디지털", ("디지털", "아이패드", "태블릿", "프로크리에이트", "포토샵", "캔바", "canva")),
    ("조형", ("클레이", "점토", "찰흙", "입체", "조소", "부조", "모형", "종이접기")),
    ("콜라주", ("콜라주", "오려", "오리기", "붙이기", "모자이크", "스크랩", "스티커")),
    ("회화", ("수채", "아크릴", "물감", "채색", "붓", "구아슈", "포스터컬러")),
    ("드로잉", ("드로잉", "스케치", "크로키", "데생", "연필", "선 그리기", "라인")),
]

GRADE_RULES = [
    ("저학년", ("저학년", "1학년", "2학년", "초1", "초2")),
    ("중학년", ("중학년", "3학년", "4학년", "초3", "초4")),
    ("고학년", ("고학년", "5학년", "6학년", "초5", "초6")),
]

MATERIAL_TAGS = {
    "색연필": ("색연필", "컬러펜슬"),
    "크레파스": ("크레파스", "오일파스텔", "파스텔"),
    "물감": ("물감", "수채", "아크릴", "구아슈", "포스터컬러"),
    "점토": ("클레이", "점토", "찰흙"),
    "종이": ("도화지", "종이", "한지", "색종이"),
    "재활용": ("재활용", "업사이클", "폐품", "분리수거"),
    "사인펜": ("사인펜", "매직", "마카", "마커"),
}

THEME_TAGS = {
    "봄": ("봄", "벚꽃", "새싹"),
    "여름": ("여름", "바다", "해변"),
    "가을": ("가을", "단풍", "낙엽"),
    "겨울": ("겨울", "눈사람", "눈꽃"),
    "동물": ("동물", "강아지", "고양이", "새", "물고기"),
    "자연": ("자연", "풍경", "산", "꽃", "나무", "숲"),
    "인물": ("인물", "자화상", "초상화", "얼굴"),
    "환경": ("환경", "기후", "지구", "탄소", "플라스틱"),
}

FORMAT_TAGS = {
    "협동": ("협동", "모둠", "팀", "공동", "함께"),
    "감상": ("감상", "작품 읽기", "토론"),
    "표현": ("표현", "창작", "만들기"),
}


def build_auto_metadata(title: str, youtube_url: str, step_texts: list[str]) -> AutoMetadata:
    title = (title or "").strip()
    text_parts = [title, youtube_url or ""] + [text or "" for text in step_texts]
    merged = "\n".join(part for part in text_parts if part).strip()
    normalized = _normalize_text(merged)

    category, category_score = _pick_best_rule(CATEGORY_RULES, normalized, fallback="표현활동")
    grade_band, grade_score = _pick_best_rule(GRADE_RULES, normalized, fallback="전체학년")
    material_tags = _collect_tags(MATERIAL_TAGS, normalized)
    theme_tags = _collect_tags(THEME_TAGS, normalized)
    format_tags = _collect_tags(FORMAT_TAGS, normalized)

    tags = _build_tags(category, grade_band, material_tags, theme_tags, format_tags)
    confidence = _calc_confidence(category_score, grade_score, tags)
    suggested_title = _build_suggested_title(title, category, grade_band, material_tags, theme_tags)
    search_text = _build_search_text(title, step_texts, tags, category, grade_band, youtube_url)

    return AutoMetadata(
        category=category,
        grade_band=grade_band,
        tags=tags,
        confidence=confidence,
        search_text=search_text,
        suggested_title=suggested_title,
    )


def apply_auto_metadata(art_class, *, save: bool = True) -> AutoMetadata:
    step_texts = list(art_class.steps.values_list("description", flat=True))
    metadata = build_auto_metadata(
        title=art_class.title or "",
        youtube_url=art_class.youtube_url or "",
        step_texts=step_texts,
    )

    art_class.auto_category = metadata.category
    art_class.auto_grade_band = metadata.grade_band
    art_class.auto_tags = metadata.tags
    art_class.auto_confidence = metadata.confidence
    art_class.search_text = metadata.search_text
    art_class.is_auto_classified = True

    update_fields = [
        "auto_category",
        "auto_grade_band",
        "auto_tags",
        "auto_confidence",
        "search_text",
        "is_auto_classified",
    ]

    if not (art_class.title or "").strip() and metadata.suggested_title:
        art_class.title = metadata.suggested_title
        update_fields.append("title")

    if save:
        art_class.save(update_fields=update_fields)

    return metadata


def collect_popular_tags(classes, *, limit: int = 12, sample_size: int = 500) -> list[str]:
    counter: Counter[str] = Counter()
    for tags in classes.values_list("auto_tags", flat=True)[:sample_size]:
        if not isinstance(tags, list):
            continue
        for tag in tags:
            if isinstance(tag, str) and tag.strip():
                counter[tag.strip()] += 1
    return [tag for tag, _ in counter.most_common(limit)]


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).lower().strip()


def _pick_best_rule(rules, text: str, fallback: str) -> tuple[str, int]:
    best_label = fallback
    best_score = 0
    for label, keywords in rules:
        score = sum(1 for keyword in keywords if keyword.lower() in text)
        if score > best_score:
            best_label = label
            best_score = score
    return best_label, best_score


def _collect_tags(tag_map: dict[str, tuple[str, ...]], text: str) -> list[str]:
    matched: list[str] = []
    for tag, keywords in tag_map.items():
        if any(keyword.lower() in text for keyword in keywords):
            matched.append(tag)
    return matched


def _build_tags(
    category: str,
    grade_band: str,
    material_tags: list[str],
    theme_tags: list[str],
    format_tags: list[str],
) -> list[str]:
    tags: list[str] = []

    for tag in [category, grade_band]:
        if tag and tag != "전체학년":
            tags.append(tag)

    tags.extend(material_tags[:4])
    tags.extend(theme_tags[:4])
    tags.extend(format_tags[:3])

    deduped: list[str] = []
    seen = set()
    for tag in tags:
        key = tag.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(tag.strip())
    return deduped


def _calc_confidence(category_score: int, grade_score: int, tags: list[str]) -> float:
    raw = 0.25
    raw += min(category_score * 0.2, 0.35)
    raw += min(grade_score * 0.15, 0.2)
    raw += min(len(tags) * 0.03, 0.2)
    return round(min(raw, 0.95), 3)


def _build_suggested_title(
    title: str,
    category: str,
    grade_band: str,
    material_tags: list[str],
    theme_tags: list[str],
) -> str:
    if title:
        return title

    parts: list[str] = []
    if grade_band and grade_band != "전체학년":
        parts.append(grade_band)
    if theme_tags:
        parts.append(theme_tags[0])
    if material_tags:
        parts.append(material_tags[0])
    if category:
        parts.append(category)

    if not parts:
        return "자동 분류 미술 수업"
    return " ".join(parts[:3]) + " 수업"


def _build_search_text(
    title: str,
    step_texts: list[str],
    tags: list[str],
    category: str,
    grade_band: str,
    youtube_url: str,
) -> str:
    chunks = [title, category, grade_band, " ".join(tags), youtube_url]
    chunks.extend(step_texts)
    text = " ".join(chunk.strip() for chunk in chunks if chunk and chunk.strip())
    return re.sub(r"\s+", " ", text).strip()
