from .models import (
    TARGET_HIGH,
    TARGET_LOW,
    TARGET_PARENT,
    TONE_CLEAR,
    TONE_FORMAL,
    TONE_WARM,
    TOPIC_ACTIVITY,
    TOPIC_EVENT,
    TOPIC_NOTICE,
    TOPIC_SAFETY,
)

TARGET_LABELS = {
    TARGET_LOW: "초등 저학년",
    TARGET_HIGH: "초등 고학년",
    TARGET_PARENT: "학부모",
}

TOPIC_LABELS = {
    TOPIC_ACTIVITY: "활동",
    TOPIC_EVENT: "행사",
    TOPIC_SAFETY: "안전",
    TOPIC_NOTICE: "알림장",
}

TONE_BY_TARGET = {
    TARGET_LOW: TONE_WARM,
    TARGET_HIGH: TONE_CLEAR,
    TARGET_PARENT: TONE_FORMAL,
}

LENGTH_SHORT = "short"
LENGTH_MEDIUM = "medium"
LENGTH_LONG = "long"

LENGTH_CHOICES = [
    (LENGTH_SHORT, "짧게"),
    (LENGTH_MEDIUM, "보통"),
    (LENGTH_LONG, "길게"),
]

LENGTH_LABELS = dict(LENGTH_CHOICES)

LENGTH_RULES = {
    LENGTH_SHORT: {
        "label": "짧게",
        "sentence_range": "2~3문장",
        "char_range": "공백 포함 80~120자",
        "min_chars": 80,
    },
    LENGTH_MEDIUM: {
        "label": "보통",
        "sentence_range": "3~4문장",
        "char_range": "공백 포함 140~220자",
        "min_chars": 140,
    },
    LENGTH_LONG: {
        "label": "길게",
        "sentence_range": "4~5문장",
        "char_range": "공백 포함 180~260자",
        "min_chars": 180,
    },
}

TARGET_RULES = {
    TARGET_LOW: (
        "저학년: 쉬운 낱말, 짧은 문장, 따뜻한 격려. 어려운 한자어/행정어 금지. "
        "문어체 공지문 유지."
    ),
    TARGET_HIGH: (
        "고학년: 유아적 표현 금지, 명확한 설명, 실천 행동 또렷하게. "
        "문어체 공지문 유지."
    ),
    TARGET_PARENT: (
        "학부모: 공손하고 신뢰감 있게. 안내 중심, 필요 시 완곡한 협조 요청. "
        "문어체 공지문 유지."
    ),
}

PROMPT_VERSION = "v6-caveman"


def get_tone_for_target(target):
    return TONE_BY_TARGET.get(target, TONE_CLEAR)


def _get_length_rule(length_style):
    return LENGTH_RULES.get(length_style, LENGTH_RULES[LENGTH_MEDIUM])


def build_system_prompt(selected_target, length_style=LENGTH_MEDIUM):
    target_rule = TARGET_RULES.get(selected_target, TARGET_RULES[TARGET_HIGH])
    length_rule = _get_length_rule(length_style)
    common_rules = (
        "역할: 대한민국 초등 담임교사.\n"
        "과업: 학교 알림장/주간학습 멘트. 최종 본문 1개만 출력.\n\n"
        "[대상]\n"
        f"- {target_rule}\n\n"
        "[분량 규칙]\n"
        f"- 선택 분량: {length_rule['label']}; {length_rule['sentence_range']}; {length_rule['char_range']}. 반복 채움 금지.\n\n"
        "[문체]\n"
        "- 문어체 공지문. 종결: ~합니다, ~습니다, ~하세요, ~바랍니다, ~다.\n"
        "- 구어체 금지: 거예요, 할 거야, 않을 거야, 해요체.\n\n"
        "[구성]\n"
        "- 도입 -> 핵심 안내 -> 부드러운 당부. 문장은 한 단락처럼 자연스럽게 연결.\n"
        "- 행동 안내 1개 이상. 이모지/과장/광고/번역투/번호/제목/인용부호 금지.\n"
    )

    if selected_target == TARGET_PARENT:
        return (
            common_rules
            + "\n[학부모]\n"
            "- 학부모가 바로 받아 읽는 가정통신문/알림장 문장.\n"
            "- 따뜻한 존댓말, 부담 큰 명령형 금지.\n"
            "- 교사 메모 금지: 운동화를 신고오도록 안내해 주세요, 전달해 주세요, 지도해 주세요.\n"
            "- 학생 행동은 '가정에서 함께 확인해 주시기 바랍니다'처럼 직접 안내.\n"
            "\n[최종 점검]\n"
            "- 조건 맞춘 최종본만. 점검/글자 수/설명 출력 금지.\n"
        )

    return (
        common_rules
        + "\n[학생]\n"
        "- 학생 눈높이의 쉬운 낱말. 행동은 바로 따라 할 수 있게.\n"
        "\n[최종 점검]\n"
        "- 조건 맞춘 최종본만. 점검/설명 출력 금지.\n"
    )


def build_user_prompt(target, topic, keywords, context_text, length_style=LENGTH_MEDIUM):
    target_label = TARGET_LABELS.get(target, target)
    topic_label = TOPIC_LABELS.get(topic, topic)
    length_rule = _get_length_rule(length_style)
    prompt = (
        f"대상: {target_label}\n"
        f"주제: {topic_label}\n"
        f"분량: {length_rule['label']} ({length_rule['sentence_range']}, {length_rule['char_range']})\n"
        f"핵심 전달사항: {keywords}\n"
        f"추가 상황: {context_text or '없음'}\n\n"
        "요구:\n"
        "- 바로 붙여넣는 본문 1개.\n"
        "- 핵심 누락 금지. 행동 안내 1개 이상.\n"
        "- 문어체 공지문. 구어체 금지. 한 단락. 설명 금지.\n"
    )

    if length_style in (LENGTH_MEDIUM, LENGTH_LONG):
        prompt += "- 상황 안내, 핵심 준비/행동 안내, 마무리 당부 포함.\n"

    if target == TARGET_PARENT:
        prompt += (
            "- 학부모에게 직접 보내는 완성 문장.\n"
            "- 안내해 주세요/전달해 주세요/지도해 주세요로 끝내지 않기.\n"
        )

    return prompt
