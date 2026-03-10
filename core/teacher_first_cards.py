import re
import unicodedata


TRAILING_SEPARATORS = {"-", "–", "—", "·", ":", "|", "/", "•"}
TECHNICAL_FRAGMENT_RE = re.compile(
    r"(https?://|www\\.|</?[a-z][^>]*>|\\.html?\\b|\\.json\\b|\\.csv\\b|\\.xlsx?\\b|\\.pdf\\b)",
    re.IGNORECASE,
)
WHITESPACE_RE = re.compile(r"\\s+")


def _normalize_text(value):
    return WHITESPACE_RE.sub(" ", str(value or "")).strip()


def _normalized_key(value):
    return _normalize_text(value).lower()


def strip_leading_service_icon_text(value):
    text = _normalize_text(value)
    if not text:
        return ""

    index = 0
    stripped_icon_prefix = False

    while index < len(text):
        char = text[index]
        category = unicodedata.category(char)

        if char in {"\ufe0f", "\u200d"}:
            stripped_icon_prefix = True
            index += 1
            continue

        if category.startswith("S"):
            stripped_icon_prefix = True
            index += 1
            continue

        if stripped_icon_prefix and (char.isspace() or char in TRAILING_SEPARATORS):
            index += 1
            continue

        break

    cleaned = text[index:].strip()
    return cleaned or text


def clean_compact_card_text(value):
    text = strip_leading_service_icon_text(value)
    if not text:
        return ""

    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\\S+", " ", text)
    text = re.sub(r"www\\.\\S+", " ", text)
    text = re.sub(r"\\b\\S+\\.(?:html?|json|csv|xlsx?|pdf)\\b", " ", text, flags=re.IGNORECASE)
    text = _normalize_text(text.strip(" -–—·:|/"))
    return text


def is_compact_card_noise(value):
    text = _normalize_text(value)
    if not text:
        return True
    return bool(TECHNICAL_FRAGMENT_RE.search(text))


def build_teacher_first_product_labels(product):
    task_label = clean_compact_card_text(getattr(product, "solve_text", ""))
    service_label = clean_compact_card_text(getattr(product, "title", ""))
    support_label = ""

    if task_label and _normalized_key(task_label) != _normalized_key(service_label):
        support_label = service_label
    else:
        task_label = service_label
        service_label = ""
        for candidate in (
            getattr(product, "result_text", ""),
            getattr(product, "lead_text", ""),
            getattr(product, "description", ""),
        ):
            candidate_text = clean_compact_card_text(candidate)
            if candidate_text and _normalized_key(candidate_text) != _normalized_key(task_label):
                support_label = candidate_text
                break

    return {
        "teacher_first_task_label": task_label,
        "teacher_first_service_label": service_label,
        "teacher_first_support_label": support_label,
    }


def build_compact_card_copy(task_label, service_label, support_label):
    title = clean_compact_card_text(task_label) or clean_compact_card_text(service_label)
    service = clean_compact_card_text(service_label)
    support = clean_compact_card_text(support_label)

    title_key = _normalized_key(title)
    card_subtitle = ""
    card_summary = ""

    for candidate in (service, support):
        candidate_key = _normalized_key(candidate)
        if not candidate:
            continue
        if candidate_key == title_key:
            continue
        if card_subtitle:
            if candidate_key == _normalized_key(card_subtitle):
                continue
            card_summary = candidate
            break
        card_subtitle = candidate

    if card_summary and is_compact_card_noise(card_summary):
        card_summary = ""
    if card_subtitle and is_compact_card_noise(card_subtitle):
        card_subtitle = ""
        if card_summary and not is_compact_card_noise(card_summary):
            card_subtitle, card_summary = card_summary, ""

    return {
        "card_title": title,
        "card_subtitle": card_subtitle,
        "card_summary": card_summary,
    }


def build_teacher_first_product_meta(product):
    labels = build_teacher_first_product_labels(product)
    card_copy = build_compact_card_copy(
        labels["teacher_first_task_label"],
        labels["teacher_first_service_label"],
        labels["teacher_first_support_label"],
    )
    return {
        **labels,
        **card_copy,
    }
