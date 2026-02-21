TOPIC_CHOICES = [
    ("orthography", "맞춤법"),
    ("spacing", "띄어쓰기"),
    ("vocabulary", "어휘 뜻"),
    ("proverb", "속담"),
    ("idiom", "관용어"),
    ("sino_idiom", "사자성어"),
    ("hanja_word", "한자어 뜻"),
    ("main_sentence", "중심문장 찾기"),
    ("sentence_order", "문장 순서 배열"),
    ("topic_title", "주제/제목 고르기"),
    ("fact_opinion", "사실/의견 구분"),
    ("eng_vocab", "영어 단어 뜻"),
    ("eng_sentence", "영어 문장 의미"),
    ("eng_cloze", "영어 빈칸 채우기"),
    ("arithmetic", "수학 연산"),
    ("pattern", "규칙 찾기"),
    ("fraction_decimal", "분수/소수 비교"),
    ("time_calendar", "시간/달력 계산"),
    ("unit_conversion", "단위 변환"),
    ("safety_common", "생활 안전 상식"),
]

TOPIC_LABELS = dict(TOPIC_CHOICES)
DEFAULT_TOPIC = "orthography"

LEGACY_TOPIC_ALIASES = {
    "general": "vocabulary",
    "korean": "main_sentence",
    "english": "eng_vocab",
    "math": "arithmetic",
    "science": "safety_common",
    "social": "fact_opinion",
}

KOREAN_TOPIC_ALIASES = {label: key for key, label in TOPIC_CHOICES}


def normalize_topic(raw_topic: str) -> str | None:
    topic = (raw_topic or "").strip().lower()
    if not topic:
        return DEFAULT_TOPIC
    if topic in TOPIC_LABELS:
        return topic
    if topic in LEGACY_TOPIC_ALIASES:
        return LEGACY_TOPIC_ALIASES[topic]

    original = (raw_topic or "").strip()
    if original in KOREAN_TOPIC_ALIASES:
        return KOREAN_TOPIC_ALIASES[original]
    return None
