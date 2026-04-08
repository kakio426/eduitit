from __future__ import annotations

import re
from typing import Iterable


ANSWER_POLICY_VERSION = "teacher-law-v2"

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
    ("몰래 녹음", "녹음 녹취"),
    ("쉬는 시간", "쉬는시간"),
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
    "주식",
    "투자",
    "창업",
    "사업자",
    "계약서 작성",
    "소장",
    "고소장",
)

ACTOR_KEYWORDS = {
    "교사": ("교사", "선생님", "담임", "담임교사", "교원"),
    "학생": ("학생", "아이", "아동", "피해학생", "가해학생"),
    "학부모": ("학부모", "보호자", "부모", "어머니", "아버지"),
    "관리자": ("학교장", "교감", "관리자", "부장", "행정실"),
}

SCENE_KEYWORDS = {
    "교실": ("교실", "학급", "반", "교내"),
    "쉬는시간": ("쉬는시간", "휴식시간", "점심시간"),
    "상담": ("상담", "면담", "상담실"),
    "수업": ("수업", "조회", "종례", "체육시간"),
    "체험학습": ("현장체험학습", "체험학습", "수학여행", "체험활동", "야외활동"),
    "SNS·단체방": ("sns", "카톡", "단체방", "학급 밴드", "밴드", "채팅방"),
}

LEGAL_ISSUE_KEYWORDS = {
    "보호의무": ("보호의무", "주의의무", "안전조치", "안전관리"),
    "법적 책임": ("책임", "법적 책임", "과실", "책임지", "문제될", "위험할"),
    "손해배상": ("손해배상", "배상", "변상", "청구"),
    "교육활동 침해": ("교육활동 침해", "교권", "민원", "폭언", "욕설", "욕", "모욕", "협박"),
    "위법성": ("위법", "처벌", "고소", "고발", "형사", "경찰", "신고할", "범죄"),
    "신고의무": ("신고", "즉시 신고", "의심", "은폐", "축소", "보고"),
    "명예훼손": ("명예훼손", "허위사실", "게시", "공개", "비방"),
    "개인정보": ("개인정보", "유출", "사진", "영상", "촬영", "동의", "초상"),
    "생활지도": ("생활지도", "훈육", "체벌", "신체 접촉", "압수", "소지품"),
    "기록관리": ("학교생활기록부", "생활기록부", "기록", "공문", "보관", "증빙", "문서"),
}

TEACHER_CONTEXT_KEYWORDS = tuple({keyword for keywords in ACTOR_KEYWORDS.values() for keyword in keywords}) + (
    "학교",
    "교실",
    "수업",
    "학생",
    "학부모",
    "보호자",
    "학급",
    "생활지도",
    "상담",
    "학교폭력",
    "체험학습",
    "쉬는시간",
)

TEACHER_LEGAL_ISSUE_KEYWORDS = tuple(
    {keyword for keywords in LEGAL_ISSUE_KEYWORDS.values() for keyword in keywords}
) + (
    "다쳤",
    "사고",
    "부상",
    "학교폭력",
    "안전",
)

INCIDENT_CONFIG = {
    "school_safety": {
        "label": "안전사고",
        "topic": "school_safety",
        "keywords": ("다쳤", "사고", "부상", "응급", "구급", "넘어", "쉬는시간", "안전"),
        "laws": ["학교안전사고 예방 및 보상에 관한 법률", "민법", "초ㆍ중등교육법"],
        "search_queries": [
            "학생 안전사고 교사 책임",
            "학교안전사고 보호의무",
            "학교안전사고 손해배상",
        ],
        "case_queries": [
            "학교안전사고 손해배상",
            "학생 안전사고 교사 과실",
        ],
        "issue_labels": ("보호의무", "법적 책임", "손해배상"),
        "scene_labels": ("교실", "쉬는시간", "수업"),
    },
    "education_activity": {
        "label": "교육활동 침해",
        "topic": "education_activity",
        "keywords": ("교육활동 침해", "교권", "민원", "폭언", "욕설", "욕", "모욕", "협박", "녹음", "녹취"),
        "laws": ["교원의 지위 향상 및 교육활동 보호를 위한 특별법", "형법"],
        "search_queries": [
            "교육활동 침해 학부모 폭언",
            "학부모 폭언 교사 대응",
            "교원 보호 모욕 명예훼손",
        ],
        "case_queries": [
            "학부모 폭언 모욕 교사",
            "교사 명예훼손 모욕",
        ],
        "issue_labels": ("교육활동 침해", "위법성", "명예훼손"),
        "scene_labels": ("상담", "교실", "SNS·단체방"),
    },
    "privacy_photo": {
        "label": "개인정보·사진",
        "topic": "privacy_photo",
        "keywords": ("개인정보", "사진", "영상", "촬영", "게시", "초상", "동의", "유출", "단체방", "sns"),
        "laws": ["개인정보 보호법", "초ㆍ중등교육법"],
        "search_queries": [
            "학생 사진 게시 개인정보",
            "학생 사진 게시 동의",
            "개인정보 보호법 학생 사진",
        ],
        "case_queries": [
            "학생 사진 게시 개인정보",
            "개인정보 유출 학교",
        ],
        "issue_labels": ("개인정보", "위법성"),
        "scene_labels": ("교실", "SNS·단체방"),
    },
    "school_violence": {
        "label": "학교폭력",
        "topic": "school_violence",
        "keywords": ("학교폭력", "학폭", "언어폭력", "괴롭힘", "사안조사", "피해학생", "가해학생", "전담기구"),
        "laws": ["학교폭력예방 및 대책에 관한 법률"],
        "search_queries": [
            "학교폭력 초기 대응 교사",
            "학교폭력 사안조사 절차",
            "학교폭력예방 및 대책에 관한 법률",
        ],
        "case_queries": [
            "학교폭력 손해배상",
            "학교폭력 교사 대응",
        ],
        "issue_labels": ("위법성", "법적 책임"),
        "scene_labels": ("교실", "수업", "SNS·단체방"),
    },
    "student_guidance": {
        "label": "생활지도",
        "topic": "student_guidance",
        "keywords": ("생활지도", "훈육", "체벌", "신체", "압수", "소지품", "지도", "교실 통제"),
        "laws": ["초ㆍ중등교육법", "교원의 학생생활지도에 관한 고시"],
        "search_queries": [
            "학생 생활지도 신체 접촉",
            "생활지도 압수 기준",
            "교원의 학생생활지도에 관한 고시",
        ],
        "case_queries": [
            "학생 생활지도 체벌",
            "교사 신체 접촉 학생지도",
        ],
        "issue_labels": ("생활지도", "위법성", "법적 책임"),
        "scene_labels": ("교실", "수업"),
    },
    "reporting_duty": {
        "label": "신고의무",
        "topic": "reporting_duty",
        "keywords": ("신고 의무", "아동학대", "즉시 신고", "의심", "은폐", "축소", "보고"),
        "laws": ["아동학대범죄의 처벌 등에 관한 특례법", "아동복지법"],
        "search_queries": [
            "아동학대 의심 교사 신고의무",
            "즉시 신고 아동학대",
            "아동복지법 신고 의무",
        ],
        "case_queries": [
            "아동학대 신고의무 교사",
            "신고의무 위반 아동학대",
        ],
        "issue_labels": ("신고의무", "위법성"),
        "scene_labels": ("교실", "상담"),
    },
    "records_docs": {
        "label": "기록·문서",
        "topic": "records_docs",
        "keywords": ("학교생활기록부", "생활기록부", "기록", "보관", "문서", "공문", "증빙"),
        "laws": ["초ㆍ중등교육법", "공공기록물 관리에 관한 법률"],
        "search_queries": [
            "학교생활기록부 기록 기준",
            "학교 문서 보관 기준",
            "공공기록물 관리에 관한 법률 학교",
        ],
        "case_queries": [
            "학교생활기록부 정정 분쟁",
            "학교 기록 문서 분쟁",
        ],
        "issue_labels": ("기록관리", "위법성"),
        "scene_labels": ("교실", "상담"),
    },
    "property_damage": {
        "label": "재산·파손",
        "topic": "property_damage",
        "keywords": ("파손", "깨졌", "부서졌", "망가졌", "변상", "배상", "물건"),
        "laws": ["민법", "초ㆍ중등교육법"],
        "search_queries": [
            "학교 물건 파손 변상 책임",
            "학생 물건 파손 손해배상",
            "민법 손해배상 파손",
        ],
        "case_queries": [
            "물건 파손 손해배상 학교",
            "학생 물건 파손 배상",
        ],
        "issue_labels": ("손해배상", "법적 책임"),
        "scene_labels": ("교실", "수업"),
    },
    "field_trip": {
        "label": "현장체험학습",
        "topic": "field_trip",
        "keywords": ("현장체험학습", "체험학습", "수학여행", "체험활동", "야외활동"),
        "laws": ["학교안전사고 예방 및 보상에 관한 법률", "민법", "초ㆍ중등교육법"],
        "search_queries": [
            "현장체험학습 안전사고 교사 책임",
            "체험학습 보호의무",
            "수학여행 사고 손해배상",
        ],
        "case_queries": [
            "체험학습 안전사고 손해배상",
            "수학여행 교사 과실",
        ],
        "issue_labels": ("보호의무", "법적 책임", "손해배상"),
        "scene_labels": ("체험학습",),
    },
}

HIGH_RISK_KEYWORDS = {
    "아동학대 의심": ("아동학대", "학대 의심"),
    "신체 제지": ("신체", "팔 잡", "밀쳤", "제압", "체벌"),
    "형사 책임 우려": ("폭행", "고소", "형사", "경찰"),
    "학교폭력 은폐·축소 우려": ("은폐", "축소", "쉬쉬"),
    "개인정보 유출 사고": ("유출", "개인정보", "사진 게시", "영상 게시"),
    "안전사고 책임 우려": ("다쳤", "사고", "부상", "손해배상", "책임"),
}

QUICK_QUESTIONS = [
    "학생 사진을 학급 밴드나 단체방에 올려도 되나요?",
    "쉬는시간에 학생이 다쳤다면 교사 책임은 어디까지 보나요?",
    "학부모의 폭언이나 녹음이 있을 때 교사는 어떻게 대응해야 하나요?",
    "학교폭력을 알게 되면 교사가 가장 먼저 해야 할 일은 무엇인가요?",
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


def _has_any_keyword(normalized: str, keywords: Iterable[str]) -> bool:
    return any(keyword.lower() in normalized for keyword in keywords)


def _unique_items(values: Iterable[str]) -> list[str]:
    items = []
    for value in values:
        compact_value = compact_text(value)
        if compact_value and compact_value not in items:
            items.append(compact_value)
    return items


def detect_risk_flags(question: str) -> list[str]:
    normalized = normalize_for_matching(question)
    flags = []
    for label, keywords in HIGH_RISK_KEYWORDS.items():
        if any(keyword.lower() in normalized for keyword in keywords):
            flags.append(label)
    return flags


def detect_actors(question: str) -> list[str]:
    normalized = normalize_for_matching(question)
    actors = []
    for label, keywords in ACTOR_KEYWORDS.items():
        if _has_any_keyword(normalized, keywords):
            actors.append(label)
    return actors


def detect_scene(question: str) -> list[str]:
    normalized = normalize_for_matching(question)
    scenes = []
    for label, keywords in SCENE_KEYWORDS.items():
        if _has_any_keyword(normalized, keywords):
            scenes.append(label)
    return scenes


def detect_legal_issues(question: str) -> list[str]:
    normalized = normalize_for_matching(question)
    issues = []
    for label, keywords in LEGAL_ISSUE_KEYWORDS.items():
        if _has_any_keyword(normalized, keywords):
            issues.append(label)
    return issues


def detect_incident_type(question: str, *, legal_issues: list[str], scene: list[str]) -> str:
    normalized = normalize_for_matching(question)
    best_incident = ""
    best_score = 0
    for incident_type, config in INCIDENT_CONFIG.items():
        score = sum(3 for keyword in config["keywords"] if keyword.lower() in normalized)
        score += sum(2 for label in config.get("issue_labels", ()) if label in legal_issues)
        score += sum(1 for label in config.get("scene_labels", ()) if label in scene)
        if score > best_score:
            best_score = score
            best_incident = incident_type
    return best_incident


def _looks_like_teacher_context_question(normalized: str) -> bool:
    return _has_any_keyword(normalized, TEACHER_CONTEXT_KEYWORDS) and _has_any_keyword(
        normalized, TEACHER_LEGAL_ISSUE_KEYWORDS
    )


def is_supported_question(question: str, *, incident_type: str) -> bool:
    normalized = normalize_for_matching(question)
    if _has_any_keyword(normalized, UNSUPPORTED_KEYWORDS):
        return False
    if incident_type:
        return True
    return _looks_like_teacher_context_question(normalized)


def build_core_query(terms: Iterable[str], normalized_question: str) -> str:
    term_list = [term for term in terms if term]
    if term_list:
        return compact_text(" ".join(term_list[:4]))
    return compact_text(normalized_question)[:120]


def _build_structured_queries(
    *,
    incident_type: str,
    actors: list[str],
    legal_issues: list[str],
    scene: list[str],
    law_hints: list[str],
    core_query: str,
    normalized_question: str,
) -> tuple[list[str], list[str]]:
    config = INCIDENT_CONFIG.get(incident_type, {})
    actor_text = " ".join(actors[:2])
    issue_text = " ".join(legal_issues[:2])
    scene_text = " ".join(scene[:1])
    incident_label = config.get("label") or ""

    search_queries = list(config.get("search_queries") or [])
    case_queries = list(config.get("case_queries") or [])

    if incident_label and issue_text:
        search_queries.append(f"{incident_label} {issue_text}")
        case_queries.append(f"{incident_label} {issue_text}")
    if actor_text and incident_label:
        search_queries.append(f"{actor_text} {incident_label}")
    if scene_text and incident_label and issue_text:
        search_queries.append(f"{scene_text} {incident_label} {issue_text}")
    if actor_text and issue_text:
        search_queries.append(f"{actor_text} {issue_text}")
        case_queries.append(f"{actor_text} {issue_text}")

    for law_name in law_hints[:2]:
        if incident_label and issue_text:
            search_queries.append(f"{incident_label} {issue_text} {law_name}")
        elif incident_label:
            search_queries.append(f"{incident_label} {law_name}")
        elif issue_text:
            search_queries.append(f"{issue_text} {law_name}")
        if actor_text and issue_text:
            search_queries.append(f"{actor_text} {issue_text} {law_name}")
        search_queries.append(law_name)
        case_queries.append(f"{law_name} {issue_text}".strip())

    if core_query:
        search_queries.append(core_query)
    if normalized_question:
        search_queries.append(normalized_question)

    return _unique_items(search_queries), _unique_items(case_queries)


def build_query_profile(question: str) -> dict:
    original_question = compact_text(question)
    normalized_question = apply_question_replacements(original_question)
    actors = detect_actors(normalized_question)
    scene = detect_scene(normalized_question)
    legal_issues = detect_legal_issues(normalized_question)
    incident_type = detect_incident_type(
        normalized_question,
        legal_issues=legal_issues,
        scene=scene,
    )
    topic = INCIDENT_CONFIG.get(incident_type, {}).get("topic", "")
    scope_supported = is_supported_question(normalized_question, incident_type=incident_type)
    risk_flags = detect_risk_flags(normalized_question)
    core_terms = tokenize_question(normalized_question)
    core_query = build_core_query(core_terms, normalized_question)
    law_hints = list(INCIDENT_CONFIG.get(incident_type, {}).get("laws", []))
    candidate_queries, case_queries = _build_structured_queries(
        incident_type=incident_type,
        actors=actors,
        legal_issues=legal_issues,
        scene=scene,
        law_hints=law_hints,
        core_query=core_query,
        normalized_question=normalized_question,
    )

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
        "incident_type": incident_type,
        "actors": actors,
        "scene": scene,
        "legal_issues": legal_issues,
        "scope_supported": scope_supported,
        "risk_flags": risk_flags,
        "core_terms": core_terms,
        "candidate_queries": candidate_queries,
        "hint_queries": law_hints,
        "default_law_hints": law_hints,
        "case_queries": case_queries,
        "search_terms": _unique_items([*actors, *scene, *legal_issues, *law_hints, *core_terms[:4]]),
        "quick_question_key": quick_question_key,
    }
