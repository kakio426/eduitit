import re

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
    "korean_orthography": "orthography",
    "korean_reading": "main_sentence",
    "english": "eng_vocab",
    "math": "arithmetic",
    "science": "safety_common",
    "social": "fact_opinion",
    "한글 맞춤법": "orthography",
    "국어 맞춤법": "orthography",
    "국어": "main_sentence",
    "독해": "main_sentence",
    "문해력": "main_sentence",
    "읽기": "main_sentence",
    "주제 찾기": "topic_title",
    "제목 찾기": "topic_title",
    "영단어": "eng_vocab",
    "영어 단어": "eng_vocab",
    "영어 문장": "eng_sentence",
    "안전": "safety_common",
}

KOREAN_TOPIC_ALIASES = {label: key for key, label in TOPIC_CHOICES}
FLEX_TOPIC_ALIASES = {
    "국어독해": "main_sentence",
    "독서": "main_sentence",
    "읽기이해": "main_sentence",
    "중심문장": "main_sentence",
    "중심내용": "main_sentence",
    "문장순서": "sentence_order",
    "문장배열": "sentence_order",
    "주제제목고르기": "topic_title",
    "주제찾기": "topic_title",
    "제목고르기": "topic_title",
    "사실의견": "fact_opinion",
    "사실과의견": "fact_opinion",
    "영어단어": "eng_vocab",
    "영어단어뜻": "eng_vocab",
    "영단어뜻": "eng_vocab",
    "영어문장": "eng_sentence",
    "영어문장의미": "eng_sentence",
    "영어빈칸": "eng_cloze",
    "빈칸채우기": "eng_cloze",
    "수학": "arithmetic",
    "수학문제": "arithmetic",
    "연산": "arithmetic",
    "규칙찾기": "pattern",
    "분수소수": "fraction_decimal",
    "시간달력": "time_calendar",
    "단위변환": "unit_conversion",
    "생활안전": "safety_common",
    "안전상식": "safety_common",
}
KEYWORD_TOPIC_ALIASES = [
    ("맞춤법", "orthography"),
    ("띄어쓰기", "spacing"),
    ("사자성어", "sino_idiom"),
    ("한자어", "hanja_word"),
    ("관용어", "idiom"),
    ("속담", "proverb"),
    ("문장순서", "sentence_order"),
    ("주제제목", "topic_title"),
    ("주제", "topic_title"),
    ("제목", "topic_title"),
    ("사실의견", "fact_opinion"),
    ("영어단어", "eng_vocab"),
    ("영어문장", "eng_sentence"),
    ("빈칸", "eng_cloze"),
    ("연산", "arithmetic"),
    ("규칙", "pattern"),
    ("분수소수", "fraction_decimal"),
    ("시간달력", "time_calendar"),
    ("단위변환", "unit_conversion"),
    ("안전", "safety_common"),
]


def _compact_topic_key(raw_text: str) -> str:
    return re.sub(r"[\s_\-/,.:;()]+", "", str(raw_text or "").strip().lower())


COMPACT_TOPIC_ALIASES = {}
for _key, _label in TOPIC_CHOICES:
    for _alias in (_key, _label):
        _compact = _compact_topic_key(_alias)
        if _compact:
            COMPACT_TOPIC_ALIASES.setdefault(_compact, _key)

for _alias, _key in LEGACY_TOPIC_ALIASES.items():
    _compact = _compact_topic_key(_alias)
    if _compact:
        COMPACT_TOPIC_ALIASES[_compact] = _key

for _alias, _key in FLEX_TOPIC_ALIASES.items():
    _compact = _compact_topic_key(_alias)
    if _compact:
        COMPACT_TOPIC_ALIASES[_compact] = _key


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

    compact = _compact_topic_key(raw_topic)
    if compact in COMPACT_TOPIC_ALIASES:
        return COMPACT_TOPIC_ALIASES[compact]

    for keyword, mapped in KEYWORD_TOPIC_ALIASES:
        compact_keyword = _compact_topic_key(keyword)
        if compact_keyword and compact_keyword in compact:
            return mapped

    return None
