import re
from urllib.parse import parse_qs, urlparse

from django.core.exceptions import ValidationError

from .models import Insight


HEADER_PATTERN = re.compile(
    r"(?im)^\s*(?P<header>"
    r"title|category|카테고리|video\s*url|thumbnail\s*url|content|kakio\s*note|tags?"
    r")\s*:\s*(?P<inline>[^\n]*)"
)

HEADER_KEY_MAP = {
    "title": "title",
    "category": "category",
    "카테고리": "category",
    "videourl": "video_url",
    "thumbnailurl": "thumbnail_url",
    "content": "content",
    "kakionote": "kakio_note",
    "tag": "tags",
    "tags": "tags",
}

CATEGORY_MAP = {
    "youtube scrap": "youtube",
    "youtube": "youtube",
    "devlog (development log)": "devlog",
    "devlog": "devlog",
    "column/essay": "column",
    "column": "column",
}


def _normalize_header(raw_header: str) -> str:
    return re.sub(r"\s+", "", raw_header.strip().lower())


def _extract_sections(raw_text: str) -> dict[str, str]:
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    matches = list(HEADER_PATTERN.finditer(text))
    sections: dict[str, str] = {}

    for idx, match in enumerate(matches):
        normalized = _normalize_header(match.group("header"))
        key = HEADER_KEY_MAP.get(normalized)
        if not key:
            continue

        next_start = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        inline = match.group("inline").strip()
        tail = text[match.end() : next_start].strip()

        value = inline
        if tail:
            value = f"{inline}\n{tail}" if inline else tail
        value = value.strip()

        if value:
            sections[key] = value

    return sections


def _extract_video_id(video_url: str) -> str:
    parsed = urlparse(video_url.strip())
    host = parsed.netloc.lower()

    if "youtu.be" in host:
        return parsed.path.strip("/").split("/")[0]

    if "youtube.com" in host:
        query = parse_qs(parsed.query)
        video_id = query.get("v", [None])[0]
        if video_id:
            return video_id

        if parsed.path.startswith("/shorts/"):
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) >= 2:
                return parts[1]

    return ""


def _normalize_video_url(video_url: str) -> str:
    video_url = video_url.strip()
    if not video_url:
        return ""

    video_id = _extract_video_id(video_url)
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return video_url


def _normalize_category(category_raw: str) -> str:
    if not category_raw:
        return "youtube"

    for token in re.split(r"[\n,]+", category_raw):
        candidate = token.strip().strip("-*•").strip()
        if not candidate:
            continue

        lowered = re.sub(r"\s+", " ", candidate.lower())
        if lowered in CATEGORY_MAP:
            return CATEGORY_MAP[lowered]
        if "youtube" in lowered:
            return "youtube"
        if "devlog" in lowered:
            return "devlog"
        if "column" in lowered:
            return "column"

    return "youtube"


def _normalize_tags(tags_raw: str) -> str:
    tags_raw = tags_raw.strip()
    if not tags_raw:
        return ""

    hashtag_parts = re.findall(r"#([^\s,#]+)", tags_raw)
    if hashtag_parts:
        tokens = [f"#{item.strip()}" for item in hashtag_parts if item.strip()]
    else:
        tokens = []
        for part in re.split(r"[,\n]+", tags_raw):
            token = part.strip().lstrip("#").replace(" ", "")
            if token:
                tokens.append(f"#{token}")

    deduped: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        cleaned = token.rstrip(".,;:")
        if not cleaned or cleaned in seen:
            continue
        deduped.append(cleaned)
        seen.add(cleaned)
    return ",".join(deduped)


def parse_pasted_insight(raw_text: str) -> dict[str, str]:
    if not raw_text or not raw_text.strip():
        raise ValueError("붙여넣기 내용이 비어 있습니다.")

    sections = _extract_sections(raw_text)
    title = sections.get("title", "").strip().strip('"').strip("'")
    content = sections.get("content", "").strip()

    if not title:
        raise ValueError("`Title:` 항목을 찾지 못했습니다.")
    if not content:
        raise ValueError("`Content:` 항목을 찾지 못했습니다.")

    video_url = _normalize_video_url(sections.get("video_url", ""))
    thumbnail_url = sections.get("thumbnail_url", "").strip()
    if not thumbnail_url and video_url:
        video_id = _extract_video_id(video_url)
        if video_id:
            thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"

    return {
        "title": title,
        "category": _normalize_category(sections.get("category", "")),
        "video_url": video_url,
        "thumbnail_url": thumbnail_url,
        "content": content,
        "kakio_note": sections.get("kakio_note", "").strip(),
        "tags": _normalize_tags(sections.get("tags", "")),
    }


def upsert_insight_from_text(raw_text: str) -> tuple[Insight, bool]:
    payload = parse_pasted_insight(raw_text)
    video_url = payload.get("video_url") or ""

    existing = None
    if video_url:
        existing = Insight.objects.filter(video_url=video_url).order_by("-id").first()

    if existing:
        for key, value in payload.items():
            setattr(existing, key, value)
        insight = existing
        created = False
    else:
        insight = Insight(**payload)
        created = True

    try:
        insight.full_clean(exclude=["likes"])
    except ValidationError as exc:
        raise ValidationError(exc.messages) from exc

    insight.save()
    return insight, created
