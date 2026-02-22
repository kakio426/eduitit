import re


_TIMESTAMP_PATTERN = re.compile(r"\[(?:\d{1,2}:)?\d{1,2}:\d{2}\]")
_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")
_BULLET_PATTERN = re.compile(r"^\s*(?:[-*•]|\d+\.)\s+")


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _normalize_inline_spacing(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text).strip()


def _join_existing_paragraphs(text: str) -> str:
    chunks = []
    for chunk in re.split(r"\n\s*\n+", text):
        lines = [_normalize_inline_spacing(line) for line in chunk.split("\n")]
        lines = [line for line in lines if line]
        if lines:
            chunks.append(" ".join(lines))
    return "\n\n".join(chunks)


def _is_bullet_only(lines: list[str]) -> bool:
    if not lines:
        return False
    return all(_BULLET_PATTERN.match(line) for line in lines)


def auto_format_insight_text(raw_text: str) -> str:
    """Make long pasted text easier to read without changing meaning."""
    if not raw_text:
        return ""

    text = _normalize_newlines(str(raw_text)).strip()
    if not text:
        return ""

    # Keep code blocks untouched.
    if "```" in text:
        return text

    if re.search(r"\n\s*\n", text):
        return _join_existing_paragraphs(text)

    lines = [_normalize_inline_spacing(line) for line in text.split("\n")]
    lines = [line for line in lines if line]
    if not lines:
        return ""

    if _is_bullet_only(lines):
        return "\n".join(lines)

    merged = _normalize_inline_spacing(" ".join(lines))

    # Split by timeline markers first.
    if _TIMESTAMP_PATTERN.search(merged):
        marked = _TIMESTAMP_PATTERN.sub(lambda m: f"\n\n{m.group(0)} ", merged).strip()
        return _join_existing_paragraphs(marked)

    sentences = [part.strip() for part in _SENTENCE_SPLIT_PATTERN.split(merged) if part.strip()]
    if len(sentences) < 3:
        return merged

    chunk_size = 2 if len(sentences) <= 10 else 3
    paragraphs = []
    for idx in range(0, len(sentences), chunk_size):
        paragraphs.append(" ".join(sentences[idx : idx + chunk_size]))

    return "\n\n".join(paragraphs)
