from __future__ import annotations

import re
from typing import Iterable


ANSWER_POLICY_VERSION = "teacher-law-v3"

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
    "학부모": ("학부모", "부모", "어머니", "아버지"),
    "보호자": ("보호자",),
    "외부인": ("외부인", "민원인", "방문객"),
    "동료교직원": ("동료교직원", "동료교사", "교직원", "행정실"),
    "관리자": ("학교장", "교감", "관리자", "부장"),
}

SCENE_OPTIONS = [
    {"value": "class_time", "label": "수업 중"},
    {"value": "break_time", "label": "쉬는시간"},
    {"value": "field_trip", "label": "체험학습"},
    {"value": "outside_classroom", "label": "교실 밖"},
]
SCENE_MAP = {item["value"]: item for item in SCENE_OPTIONS}
SCENE_KEYWORDS = {
    "수업 중": ("수업", "조회", "종례", "체육시간"),
    "쉬는시간": ("쉬는시간", "휴식시간", "점심시간"),
    "체험학습": ("현장체험학습", "체험학습", "수학여행", "체험활동", "야외활동"),
    "교실 밖": ("복도", "운동장", "급식실", "교실 밖", "교외"),
    "상담": ("상담", "면담", "상담실"),
    "SNS·단체방": ("sns", "카톡", "단체방", "학급 밴드", "밴드", "채팅방"),
}

COUNTERPART_OPTIONS = [
    {"value": "student", "label": "학생", "actor": "학생"},
    {"value": "parent", "label": "학부모", "actor": "학부모"},
    {"value": "guardian", "label": "보호자", "actor": "보호자"},
    {"value": "outsider", "label": "외부인", "actor": "외부인"},
    {"value": "staff", "label": "동료교직원", "actor": "동료교직원"},
]
COUNTERPART_MAP = {item["value"]: item for item in COUNTERPART_OPTIONS}

LEGAL_GOAL_OPTIONS = [
    {
        "value": "immediate_action",
        "label": "지금 바로 해야 할 일",
        "issue_labels": (),
        "grep_terms": ("초기 대응", "우선 조치", "즉시 해야 할 일"),
    },
    {
        "value": "teacher_liability",
        "label": "교사 책임이 있는지",
        "issue_labels": ("법적 책임", "손해배상", "보호의무"),
        "grep_terms": ("교사 책임", "과실", "손해배상", "보호의무"),
    },
    {
        "value": "legal_risk",
        "label": "위법·처벌 위험이 있는지",
        "issue_labels": ("위법성", "교육활동 침해", "명예훼손"),
        "grep_terms": ("위법", "처벌", "형사 책임", "폭행", "상해", "모욕", "명예훼손"),
    },
    {
        "value": "reporting_duty",
        "label": "신고·보고 의무가 있는지",
        "issue_labels": ("신고의무",),
        "grep_terms": ("신고 의무", "보고 의무", "즉시 신고"),
    },
    {
        "value": "posting_allowed",
        "label": "게시·기록·공개가 가능한지",
        "issue_labels": ("개인정보", "명예훼손", "기록관리"),
        "grep_terms": ("게시 가능", "공개 가능", "기록 가능", "동의", "촬영", "게시"),
    },
]
LEGAL_GOAL_MAP = {item["value"]: item for item in LEGAL_GOAL_OPTIONS}

INCIDENT_OPTIONS = [
    {
        "value": "school_safety",
        "label": "안전사고·책임",
        "topic": "school_safety",
        "requires": "scene",
        "keywords": ("다쳤", "사고", "부상", "응급", "구급", "넘어", "안전", "다친"),
        "laws": ["학교안전사고 예방 및 보상에 관한 법률", "민법", "초ㆍ중등교육법"],
        "default_issues": ("보호의무", "법적 책임", "손해배상"),
        "case_queries": ("학교안전사고 손해배상", "학생 안전사고 교사 과실"),
    },
    {
        "value": "education_activity",
        "label": "교육활동 침해·폭언·폭행",
        "topic": "education_activity",
        "requires": "counterpart",
        "keywords": (
            "교육활동 침해",
            "교권",
            "민원",
            "폭언",
            "욕설",
            "욕",
            "모욕",
            "협박",
            "항의",
            "폭행",
            "상해",
            "때렸",
            "맞았",
            "구타",
            "손찌검",
            "밀쳤",
        ),
        "laws": ["교원의 지위 향상 및 교육활동 보호를 위한 특별법", "형법"],
        "default_issues": ("교육활동 침해", "위법성", "폭행"),
        "case_queries": ("교사 폭행 형법", "교육활동 침해 교사 폭행"),
    },
    {
        "value": "recording_defamation",
        "label": "녹음·명예훼손·공개",
        "topic": "education_activity",
        "requires": "counterpart",
        "keywords": ("녹음", "녹취", "명예훼손", "허위사실", "비방", "공개", "게시", "퍼뜨"),
        "laws": ["형법", "개인정보 보호법"],
        "default_issues": ("위법성", "명예훼손", "개인정보"),
        "case_queries": ("교사 명예훼손 녹음 공개", "무단 녹음 공개 학교"),
    },
    {
        "value": "privacy_photo",
        "label": "개인정보·사진·영상",
        "topic": "privacy_photo",
        "requires": "counterpart",
        "keywords": ("개인정보", "사진", "영상", "촬영", "게시", "초상", "동의", "유출"),
        "laws": ["개인정보 보호법", "초ㆍ중등교육법"],
        "default_issues": ("개인정보", "위법성"),
        "case_queries": ("학생 사진 게시 개인정보", "개인정보 유출 학교"),
    },
    {
        "value": "student_guidance",
        "label": "생활지도·체벌·압수",
        "topic": "student_guidance",
        "requires": "",
        "keywords": ("생활지도", "훈육", "체벌", "신체", "압수", "소지품", "지도", "통제"),
        "laws": ["초ㆍ중등교육법", "교원의 학생생활지도에 관한 고시"],
        "default_issues": ("생활지도", "위법성", "법적 책임"),
        "case_queries": ("학생 생활지도 체벌", "교사 신체 접촉 학생지도"),
    },
    {
        "value": "school_violence",
        "label": "학교폭력",
        "topic": "school_violence",
        "requires": "scene",
        "keywords": ("학교폭력", "학폭", "언어폭력", "괴롭힘", "사안조사", "피해학생", "가해학생", "전담기구"),
        "laws": ["학교폭력예방 및 대책에 관한 법률"],
        "default_issues": ("위법성", "법적 책임"),
        "case_queries": ("학교폭력 손해배상", "학교폭력 교사 대응"),
    },
    {
        "value": "reporting_duty",
        "label": "신고의무·아동학대",
        "topic": "reporting_duty",
        "requires": "",
        "keywords": ("신고 의무", "아동학대", "즉시 신고", "의심", "은폐", "축소", "보고"),
        "laws": ["아동학대범죄의 처벌 등에 관한 특례법", "아동복지법"],
        "default_issues": ("신고의무", "위법성"),
        "case_queries": ("아동학대 신고의무 교사", "신고의무 위반 아동학대"),
    },
    {
        "value": "records_docs",
        "label": "기록·문서",
        "topic": "records_docs",
        "requires": "",
        "keywords": ("학교생활기록부", "생활기록부", "기록", "보관", "문서", "공문", "증빙"),
        "laws": ["초ㆍ중등교육법", "공공기록물 관리에 관한 법률"],
        "default_issues": ("기록관리", "위법성"),
        "case_queries": ("학교생활기록부 정정 분쟁", "학교 기록 문서 분쟁"),
    },
]
INCIDENT_MAP = {item["value"]: item for item in INCIDENT_OPTIONS}

HIGH_RISK_KEYWORDS = {
    "아동학대 의심": ("아동학대", "학대 의심"),
    "신체 제지": ("신체", "팔 잡", "밀쳤", "제압", "체벌"),
    "형사 책임 우려": ("폭행", "고소", "형사", "경찰"),
    "학교폭력 은폐·축소 우려": ("은폐", "축소", "쉬쉬"),
    "개인정보 유출 사고": ("유출", "개인정보", "사진 게시", "영상 게시"),
    "안전사고 책임 우려": ("다쳤", "사고", "부상", "손해배상", "책임"),
}

PHYSICAL_VIOLENCE_KEYWORDS = ("폭행", "상해", "때렸", "맞았", "구타", "손찌검", "밀쳤")

QUICK_QUESTION_PRESETS = [
    {
        "key": "privacy-photo-posting",
        "question": "학생 사진을 학급 밴드나 단체방에 올려도 되나요?",
        "incident_type": "privacy_photo",
        "legal_goal": "posting_allowed",
        "counterpart": "student",
        "scene": "",
    },
    {
        "key": "school-safety-break-time",
        "question": "쉬는시간에 학생이 다쳤다면 교사 책임은 어디까지 보나요?",
        "incident_type": "school_safety",
        "legal_goal": "teacher_liability",
        "scene": "break_time",
        "counterpart": "",
    },
    {
        "key": "education-activity-parent-abuse",
        "question": "학부모의 폭언이나 녹음이 있을 때 교사는 어떻게 대응해야 하나요?",
        "incident_type": "education_activity",
        "legal_goal": "immediate_action",
        "counterpart": "parent",
        "scene": "",
    },
    {
        "key": "school-violence-first-action",
        "question": "학교폭력을 알게 되면 교사가 가장 먼저 해야 할 일은 무엇인가요?",
        "incident_type": "school_violence",
        "legal_goal": "immediate_action",
        "scene": "class_time",
        "counterpart": "",
    },
]
QUICK_QUESTIONS = [item["question"] for item in QUICK_QUESTION_PRESETS]

LEGAL_ISSUE_KEYWORDS = {
    "보호의무": ("보호의무", "주의의무", "안전조치", "안전관리"),
    "법적 책임": ("책임", "법적 책임", "과실", "책임지", "문제될", "위험할"),
    "손해배상": ("손해배상", "배상", "변상", "청구"),
    "교육활동 침해": ("교육활동 침해", "교권", "민원", "폭언", "욕설", "욕", "모욕", "협박", "폭행", "상해"),
    "위법성": ("위법", "처벌", "고소", "고발", "형사", "경찰", "신고할", "범죄", "폭행", "상해", "때렸", "맞았"),
    "폭행": ("폭행", "상해", "때렸", "맞았", "구타", "손찌검", "밀쳤", "폭행죄", "상해죄"),
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

TEACHER_LEGAL_ISSUE_KEYWORDS = tuple({keyword for keywords in LEGAL_ISSUE_KEYWORDS.values() for keyword in keywords}) + (
    "다쳤",
    "사고",
    "부상",
    "학교폭력",
    "안전",
)


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


def _unique_items(values: Iterable[str]) -> list[str]:
    items = []
    for value in values:
        compact_value = compact_text(value)
        if compact_value and compact_value not in items:
            items.append(compact_value)
    return items


def _has_any_keyword(normalized: str, keywords: Iterable[str]) -> bool:
    return any(keyword.lower() in normalized for keyword in keywords)


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


def infer_legal_goal(question: str, *, legal_issues: list[str]) -> str:
    normalized = normalize_for_matching(question)
    if any(keyword in normalized for keyword in ("먼저", "바로", "즉시", "대응")):
        return "immediate_action"
    if "신고의무" in legal_issues or "보고" in normalized or "신고" in normalized:
        return "reporting_duty"
    if any(keyword in normalized for keyword in ("책임", "과실", "배상", "손해배상")):
        return "teacher_liability"
    if any(keyword in normalized for keyword in ("게시", "공개", "올려", "기록", "촬영")):
        return "posting_allowed"
    if any(keyword in normalized for keyword in ("적용되는 법", "어떤 법", "무슨 법", "적용되나", "적용되나요")):
        return "legal_risk"
    if "위법성" in legal_issues or any(keyword in normalized for keyword in ("처벌", "위법", "고소")):
        return "legal_risk"
    return ""


def detect_incident_type(question: str, *, legal_issues: list[str], scene: list[str]) -> str:
    normalized = normalize_for_matching(question)
    best_incident = ""
    best_score = 0
    for option in INCIDENT_OPTIONS:
        score = sum(3 for keyword in option["keywords"] if keyword.lower() in normalized)
        score += sum(2 for label in option.get("default_issues", ()) if label in legal_issues)
        score += sum(1 for label in scene if label in normalized or label in option["label"])
        if score > best_score:
            best_score = score
            best_incident = option["value"]
    return best_incident


def _looks_like_teacher_context_question(normalized: str) -> bool:
    return _has_any_keyword(normalized, TEACHER_CONTEXT_KEYWORDS) and _has_any_keyword(
        normalized, TEACHER_LEGAL_ISSUE_KEYWORDS
    )


def _has_physical_violence_context(normalized_question: str, legal_issues: list[str]) -> bool:
    return "폭행" in legal_issues or _has_any_keyword(normalized_question, PHYSICAL_VIOLENCE_KEYWORDS)


def is_supported_question(question: str, *, incident_type: str) -> bool:
    normalized = normalize_for_matching(question)
    if incident_type:
        return True
    if _has_any_keyword(normalized, UNSUPPORTED_KEYWORDS):
        return False
    return _looks_like_teacher_context_question(normalized)


def build_core_query(terms: Iterable[str], normalized_question: str) -> str:
    term_list = [term for term in terms if term]
    if term_list:
        return compact_text(" ".join(term_list[:4]))
    return compact_text(normalized_question)[:120]


def get_input_options() -> dict:
    return {
        "incident_options": [dict(option) for option in INCIDENT_OPTIONS],
        "legal_goal_options": [dict(option) for option in LEGAL_GOAL_OPTIONS],
        "scene_options": [dict(option) for option in SCENE_OPTIONS],
        "counterpart_options": [
            {"value": item["value"], "label": item["label"]}
            for item in COUNTERPART_OPTIONS
        ],
    }


def get_quick_question_presets() -> list[dict]:
    return [dict(item) for item in QUICK_QUESTION_PRESETS]


def validate_structured_input(*, incident_type: str, legal_goal: str, scene: str = "", counterpart: str = "") -> dict:
    field_errors = {}
    incident = INCIDENT_MAP.get(compact_text(incident_type))
    goal = LEGAL_GOAL_MAP.get(compact_text(legal_goal))

    if not incident:
        field_errors["incident_type"] = "사건 유형을 먼저 골라 주세요."
    if not goal:
        field_errors["legal_goal"] = "지금 궁금한 것을 먼저 골라 주세요."

    requires = (incident or {}).get("requires") or ""
    if requires == "scene":
        if compact_text(scene) not in SCENE_MAP:
            field_errors["scene"] = "장면을 하나 골라 주세요."
    if requires == "counterpart":
        if compact_text(counterpart) not in COUNTERPART_MAP:
            field_errors["counterpart"] = "상대를 하나 골라 주세요."
    return field_errors


def _match_quick_question_key(
    normalized_question: str,
    *,
    incident_type: str,
    legal_goal: str,
    scene: str,
    counterpart: str,
) -> str:
    normalized_matching = normalize_for_matching(normalized_question)
    for preset in QUICK_QUESTION_PRESETS:
        if normalize_for_matching(apply_question_replacements(preset["question"])) != normalized_matching:
            continue
        if preset["incident_type"] != incident_type:
            continue
        if preset["legal_goal"] != legal_goal:
            continue
        if compact_text(preset.get("scene")) != compact_text(scene):
            continue
        if compact_text(preset.get("counterpart")) != compact_text(counterpart):
            continue
        return preset["key"]
    return ""


def _build_candidate_queries(
    *,
    incident_label: str,
    legal_goal_label: str,
    scene_label: str,
    counterpart_label: str,
    law_hints: list[str],
    core_query: str,
    normalized_question: str,
) -> list[str]:
    queries = []
    if incident_label and legal_goal_label:
        queries.append(f"{incident_label} {legal_goal_label}")
    if scene_label and incident_label and legal_goal_label:
        queries.append(f"{scene_label} {incident_label} {legal_goal_label}")
    if counterpart_label and incident_label and legal_goal_label:
        queries.append(f"{counterpart_label} {incident_label} {legal_goal_label}")
    for law_name in law_hints[:2]:
        queries.append(f"{incident_label} {legal_goal_label} {law_name}".strip())
        queries.append(law_name)
    if core_query:
        queries.append(core_query)
    if normalized_question:
        queries.append(normalized_question)
    return _unique_items(queries)


def _build_case_queries(
    *,
    incident_label: str,
    legal_goal_label: str,
    counterpart_label: str,
    law_hints: list[str],
    config: dict,
) -> list[str]:
    queries = list(config.get("case_queries") or [])
    if incident_label and legal_goal_label:
        queries.append(f"{incident_label} {legal_goal_label}")
    if counterpart_label and legal_goal_label:
        queries.append(f"{counterpart_label} {legal_goal_label}")
    for law_name in law_hints[:1]:
        queries.append(f"{law_name} {legal_goal_label}".strip())
    return _unique_items(queries)


def _build_law_query_hint(
    *,
    incident_label: str,
    legal_goal_terms: tuple[str, ...],
    scene_label: str,
    counterpart_label: str,
    core_terms: list[str],
) -> str:
    return compact_text(
        " ".join(
            _unique_items(
                [
                    incident_label,
                    *legal_goal_terms[:3],
                    scene_label,
                    counterpart_label,
                    *core_terms[:3],
                ]
            )
        )
    )


def build_query_profile(
    question: str,
    *,
    incident_type: str = "",
    legal_goal: str = "",
    scene: str = "",
    counterpart: str = "",
) -> dict:
    original_question = compact_text(question)
    normalized_question = apply_question_replacements(original_question)
    normalized_matching = normalize_for_matching(normalized_question)
    core_terms = tokenize_question(normalized_question)
    core_query = build_core_query(core_terms, normalized_question)

    detected_scene = detect_scene(normalized_question)
    detected_issues = detect_legal_issues(normalized_question)
    incident_key = compact_text(incident_type)
    goal_key = compact_text(legal_goal)
    scene_key = compact_text(scene)
    counterpart_key = compact_text(counterpart)

    if incident_key not in INCIDENT_MAP:
        incident_key = detect_incident_type(
            normalized_question,
            legal_issues=detected_issues,
            scene=detected_scene,
        )
    if goal_key not in LEGAL_GOAL_MAP:
        goal_key = infer_legal_goal(normalized_question, legal_issues=detected_issues)

    incident = INCIDENT_MAP.get(incident_key, {})
    goal = LEGAL_GOAL_MAP.get(goal_key, {})
    topic = incident.get("topic", "")
    scope_supported = is_supported_question(normalized_question, incident_type=incident_key)
    risk_flags = detect_risk_flags(normalized_question)

    scene_values = []
    if scene_key in SCENE_MAP:
        scene_values.append(SCENE_MAP[scene_key]["label"])
    scene_values.extend(label for label in detected_scene if label not in scene_values)
    counterpart_label = COUNTERPART_MAP.get(counterpart_key, {}).get("label", "")
    counterpart_actor = COUNTERPART_MAP.get(counterpart_key, {}).get("actor", "")

    actors = detect_actors(normalized_question)
    if counterpart_actor and counterpart_actor not in actors:
        actors.append(counterpart_actor)
    if "교사" not in actors:
        actors.insert(0, "교사")

    legal_issues = _unique_items([*goal.get("issue_labels", ()), *incident.get("default_issues", ()), *detected_issues])
    law_hints = list(incident.get("laws") or [])
    incident_label = incident.get("label", "")
    legal_goal_label = goal.get("label", "")
    scene_label = SCENE_MAP.get(scene_key, {}).get("label", "")
    candidate_queries = _build_candidate_queries(
        incident_label=incident_label,
        legal_goal_label=legal_goal_label,
        scene_label=scene_label,
        counterpart_label=counterpart_label,
        law_hints=law_hints,
        core_query=core_query,
        normalized_question=normalized_question,
    )
    case_queries = _build_case_queries(
        incident_label=incident_label,
        legal_goal_label=legal_goal_label,
        counterpart_label=counterpart_label,
        law_hints=law_hints,
        config=incident,
    )
    law_query_hint = _build_law_query_hint(
        incident_label=incident_label,
        legal_goal_terms=tuple(goal.get("grep_terms") or ()),
        scene_label=scene_label,
        counterpart_label=counterpart_label,
        core_terms=core_terms,
    )
    if _has_physical_violence_context(normalized_question, legal_issues):
        legal_issues = _unique_items(["폭행", *legal_issues])
        law_hints = _unique_items(["형법", *law_hints])
        violence_terms = _unique_items(
            [
                compact_text(f"{counterpart_label} 교사 폭행") if counterpart_label else "교사 폭행",
                "교육활동 침해 폭행",
                "형법 폭행",
                "형사 책임 폭행",
            ]
        )
        candidate_queries = _unique_items([*violence_terms, *candidate_queries])
        case_queries = _unique_items([*violence_terms, *case_queries])
        law_query_hint = compact_text(" ".join(_unique_items([law_query_hint, "폭행", "상해", "형법"])))
    quick_question_key = _match_quick_question_key(
        normalized_question,
        incident_type=incident_key,
        legal_goal=goal_key,
        scene=scene_key,
        counterpart=counterpart_key,
    )

    return {
        "original_question": original_question,
        "normalized_question": normalized_question,
        "normalized_matching_question": normalized_matching,
        "topic": topic,
        "incident_type": incident_key,
        "incident_label": incident_label,
        "legal_goal": goal_key,
        "legal_goal_label": legal_goal_label,
        "scene": scene_values,
        "scene_value": scene_key,
        "counterpart": counterpart_key,
        "counterpart_label": counterpart_label,
        "actors": actors,
        "legal_issues": legal_issues,
        "scope_supported": scope_supported,
        "risk_flags": risk_flags,
        "core_terms": core_terms,
        "candidate_queries": candidate_queries,
        "hint_queries": law_hints,
        "default_law_hints": law_hints,
        "law_allowlist": law_hints,
        "law_query_hint": law_query_hint,
        "case_queries": case_queries,
        "search_terms": _unique_items(
            [
                incident_label,
                legal_goal_label,
                scene_label,
                counterpart_label,
                *legal_issues,
                *law_hints,
                *core_terms[:4],
            ]
        ),
        "quick_question_key": quick_question_key,
        "requires_scene": incident.get("requires") == "scene",
        "requires_counterpart": incident.get("requires") == "counterpart",
    }
