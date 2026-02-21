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

TARGET_RULES = {
    TARGET_LOW: (
        "학생(저학년) 버전: 쉬운 단어를 사용하고 문장을 짧게 작성합니다. "
        "따뜻한 격려를 포함하고 어려운 한자어/행정용어를 사용하지 않습니다."
    ),
    TARGET_HIGH: (
        "학생(고학년) 버전: 너무 유아적이지 않게 명확하게 작성합니다. "
        "이해 가능한 수준의 설명을 포함하고 실천 행동을 또렷하게 제시합니다."
    ),
    TARGET_PARENT: (
        "학부모 버전: 공손하고 신뢰감 있는 어조를 사용합니다. "
        "안내 중심으로 작성하고 필요 시 협조 요청을 포함할 수 있습니다."
    ),
}

PROMPT_VERSION = "v1"


def get_tone_for_target(target):
    return TONE_BY_TARGET.get(target, TONE_CLEAR)


def build_system_prompt(selected_target):
    target_rule = TARGET_RULES.get(selected_target, TARGET_RULES[TARGET_HIGH])
    return (
        "당신은 대한민국 초등학교 담임교사입니다.\n"
        "출력은 반드시 2~3줄, 3문장 이내로 작성합니다.\n"
        "주제는 [활동/행사/안전/알림장] 중 선택된 항목에 맞게 작성합니다.\n\n"
        "[대상 선택 규칙]\n"
        f"- {target_rule}\n\n"
        "[공통 규칙]\n"
        "- 과도한 이모지, 과장된 표현, 광고성 문장 금지.\n"
        "- 구체적 행동 안내가 1개 이상 포함되도록 작성.\n"
        "- 학교 현장에서 바로 사용할 수 있는 자연스러운 한국어 사용.\n"
        "- 번호 목록, 해시태그, 인용부호 장식 표현 금지.\n"
    )


def build_user_prompt(target, topic, keywords, context_text):
    target_label = TARGET_LABELS.get(target, target)
    topic_label = TOPIC_LABELS.get(topic, topic)
    return (
        f"대상: {target_label}\n"
        f"주제: {topic_label}\n"
        f"핵심 전달사항: {keywords}\n"
        f"추가 상황: {context_text or '없음'}\n\n"
        "요구사항:\n"
        "1) 실제 학교 알림장에 바로 붙여넣을 수 있게 작성하세요.\n"
        "2) 행동 안내를 반드시 1개 이상 넣으세요.\n"
        "3) 출력은 문장 본문만 제공하고, 부연 설명은 쓰지 마세요.\n"
    )

