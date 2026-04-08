from __future__ import annotations

import re
from typing import Iterable


ANSWER_POLICY_VERSION = "teacher-law-v1"

QUESTION_REPLACEMENTS = (
    ("학폭", "학교폭력"),
    ("생기부", "학교생활기록부"),
    ("교권 침해", "교육활동 침해"),
    ("초상권", "사진 게시 영상 게시 초상 관련"),
    ("민원", "학부모 민원 민원 응대"),
    ("욕설", "욕설 폭언 모욕"),
    ("폭언", "폭언 욕설 모욕"),
    ("막말", "막말 폭언 모욕"),
    ("반톡", "학급 채팅방"),
    ("학부모톡", "학부모 채팅"),
)

STOPWORDS = {
    "그",
    "이",
    "저",
    "좀",
    "수",
    "때",
    "것",
    "건",
    "관련",
    "문의",
    "질문",
    "하고",
    "하면",
    "해야",
    "어떻게",
    "되나요",
    "될까요",
    "가능한가요",
    "가능할까요",
    "알려주세요",
    "궁금합니다",
    "교사",
    "선생님",
    "학생",
    "학교",
}

UNSUPPORTED_KEYWORDS = (
    "중고거래",
    "환불",
    "부동산",
    "전세",
    "월세",
    "상속",
    "이혼",
    "세금",
    "세무",
    "교통사고",
    "주식",
    "투자",
    "창업",
    "사업자",
    "계약서 작성",
    "소장",
    "판례",
    "고소장",
)

TEACHER_CONTEXT_KEYWORDS = (
    "교사",
    "선생님",
    "학교",
    "교실",
    "수업",
    "학생",
    "학부모",
    "보호자",
    "학급",
    "반",
    "상담",
    "생활지도",
    "학교장",
    "담임",
)

TEACHER_LEGAL_ISSUE_KEYWORDS = (
    "민원",
    "폭언",
    "욕설",
    "욕",
    "막말",
    "모욕",
    "협박",
    "명예훼손",
    "녹음",
    "녹취",
    "고소",
    "고발",
    "신고",
    "경찰",
    "아동학대",
    "학대",
    "개인정보",
    "유출",
    "사진",
    "영상",
    "촬영",
    "게시",
    "동의",
    "체벌",
    "신체",
    "압수",
    "공문",
    "기록",
    "생기부",
    "학교생활기록부",
    "교권",
    "교육활동 침해",
    "법령",
    "법적",
    "위법",
    "처벌",
    "손해배상",
)

TOPIC_CONFIG = {
    "school_violence": {
        "keywords": ("학교폭력", "사안조사", "피해학생", "가해학생", "전담기구", "학교장 자체해결", "언어폭력", "괴롭힘"),
        "hints": ["학교폭력예방 및 대책에 관한 법률"],
    },
    "privacy_photo": {
        "keywords": ("개인정보", "사진", "영상", "촬영", "게시", "초상", "학급 밴드", "sns", "단체방", "동의서"),
        "hints": ["개인정보 보호법", "초ㆍ중등교육법"],
    },
    "student_guidance": {
        "keywords": ("생활지도", "훈육", "체벌", "신체", "압수", "소지품", "지도", "교실 통제"),
        "hints": ["초ㆍ중등교육법", "교원의 학생생활지도에 관한 고시"],
    },
    "education_activity": {
        "keywords": (
            "교육활동 침해",
            "교권",
            "악성 민원",
            "학부모 민원",
            "보호조치",
            "교원 보호",
            "폭언",
            "욕설",
            "욕",
            "막말",
            "모욕",
            "협박",
            "녹음",
            "녹취",
            "명예훼손",
            "상담 중",
            "상담중",
            "학부모 상담",
        ),
        "hints": ["교원의 지위 향상 및 교육활동 보호를 위한 특별법", "형법"],
    },
    "reporting_duty": {
        "keywords": ("신고 의무", "아동학대", "즉시 신고", "의심", "은폐", "축소", "보고"),
        "hints": ["아동학대범죄의 처벌 등에 관한 특례법", "아동복지법"],
    },
    "records_docs": {
        "keywords": ("학교생활기록부", "생활기록부", "기록", "보관", "문서", "공문", "증빙"),
        "hints": ["초ㆍ중등교육법", "공공기록물 관리에 관한 법률"],
    },
}

HIGH_RISK_KEYWORDS = {
    "아동학대 의심": ("아동학대", "학대 의심"),
    "신체 제지": ("신체", "팔 잡", "밀쳤", "제압", "체벌"),
    "형사 책임 우려": ("폭행", "고소", "형사", "경찰"),
    "학교폭력 은폐·축소 우려": ("은폐", "축소", "쉬쉬"),
    "개인정보 유출 사고": ("유출", "개인정보", "사진 게시", "영상 게시"),
}

QUICK_QUESTIONS = [
    "학생 사진을 학급 밴드나 단체방에 올려도 되나요?",
    "학교폭력을 알게 되면 교사가 가장 먼저 해야 할 일은 무엇인가요?",
    "학부모의 과도한 민원이나 폭언이 있을 때 교사는 어떻게 대응해야 하나요?",
    "학생 생활지도 중 신체 접촉이 문제가 될 수 있는 기준이 있나요?",
]


def compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalize_for_matching(value: str) -> str:
    return compact_text(value).lower()


def apply_question_replacements(question: str) -> str:
    normalized = compact_text(question)
    for source, replacement in QUESTION_REPLACEMENTS:
        normalized = normalized.replace(source, replacement)
    return compact_text(normalized)


def tokenize_question(value: str) -> list[str]:
    tokens = []
    for token in re.findall(r"[0-9A-Za-z가-힣]+", str(value or "")):
        lowered = token.lower()
        if lowered in STOPWORDS or len(lowered) <= 1:
            continue
        if lowered not in tokens:
            tokens.append(lowered)
    return tokens


def detect_topic(question: str) -> str:
    normalized = normalize_for_matching(question)
    best_topic = ""
    best_score = 0
    for topic, config in TOPIC_CONFIG.items():
        score = sum(1 for keyword in config["keywords"] if keyword.lower() in normalized)
        if score > best_score:
            best_score = score
            best_topic = topic
    return best_topic


def detect_risk_flags(question: str) -> list[str]:
    normalized = normalize_for_matching(question)
    flags = []
    for label, keywords in HIGH_RISK_KEYWORDS.items():
        if any(keyword.lower() in normalized for keyword in keywords):
            flags.append(label)
    return flags


def _has_any_keyword(normalized: str, keywords: Iterable[str]) -> bool:
    return any(keyword.lower() in normalized for keyword in keywords)


def _looks_like_teacher_context_question(normalized: str) -> bool:
    return _has_any_keyword(normalized, TEACHER_CONTEXT_KEYWORDS) and _has_any_keyword(normalized, TEACHER_LEGAL_ISSUE_KEYWORDS)


def is_supported_question(question: str, *, topic: str) -> bool:
    normalized = normalize_for_matching(question)
    if _has_any_keyword(normalized, UNSUPPORTED_KEYWORDS):
        return False
    if topic:
        return True
    if _looks_like_teacher_context_question(normalized):
        return True
    return any(keyword.lower() in normalized for config in TOPIC_CONFIG.values() for keyword in config["keywords"])


def build_core_query(terms: Iterable[str], normalized_question: str) -> str:
    term_list = [term for term in terms if term]
    if term_list:
        return compact_text(" ".join(term_list[:4]))
    return compact_text(normalized_question)[:120]


def build_query_profile(question: str) -> dict:
    original_question = compact_text(question)
    normalized_question = apply_question_replacements(original_question)
    topic = detect_topic(normalized_question)
    scope_supported = is_supported_question(normalized_question, topic=topic)
    risk_flags = detect_risk_flags(normalized_question)
    core_terms = tokenize_question(normalized_question)
    core_query = build_core_query(core_terms, normalized_question)
    hint_queries = list(TOPIC_CONFIG.get(topic, {}).get("hints", []))

    candidate_queries = []
    candidate_seed_items = [core_query]
    for hint in hint_queries[:2]:
        candidate_seed_items.append(f"{core_query} {hint}".strip())
    candidate_seed_items.extend(hint_queries[:2])

    for item in candidate_seed_items:
        compact_item = compact_text(item)
        if compact_item and compact_item not in candidate_queries:
            candidate_queries.append(compact_item)

    quick_question_key = ""
    normalized_matching = normalize_for_matching(normalized_question)
    for quick_question in QUICK_QUESTIONS:
        if normalize_for_matching(apply_question_replacements(quick_question)) == normalized_matching:
            quick_question_key = normalized_matching
            break

    return {
        "original_question": original_question,
        "normalized_question": normalized_question,
        "normalized_matching_question": normalized_matching,
        "topic": topic,
        "scope_supported": scope_supported,
        "risk_flags": risk_flags,
        "core_terms": core_terms,
        "candidate_queries": candidate_queries,
        "hint_queries": hint_queries,
        "quick_question_key": quick_question_key,
    }
