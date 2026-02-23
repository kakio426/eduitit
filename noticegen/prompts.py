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
    },
    LENGTH_MEDIUM: {
        "label": "보통",
        "sentence_range": "3~4문장",
        "char_range": "공백 포함 120~180자",
    },
    LENGTH_LONG: {
        "label": "길게",
        "sentence_range": "4~5문장",
        "char_range": "공백 포함 180~260자",
    },
}

TARGET_RULES = {
    TARGET_LOW: (
        "학생(저학년) 버전: 쉬운 단어를 사용하고 문장을 짧게 작성합니다. "
        "따뜻한 격려를 포함하고 어려운 한자어/행정용어를 사용하지 않습니다. "
        "문어체 공지문 문체(예: ~합니다, ~습니다, ~하세요, ~다)를 사용하고 구어체를 쓰지 않습니다."
    ),
    TARGET_HIGH: (
        "학생(고학년) 버전: 너무 유아적이지 않게 명확하게 작성합니다. "
        "이해 가능한 수준의 설명을 포함하고 실천 행동을 또렷하게 제시합니다. "
        "문어체 공지문 문체(예: ~합니다, ~습니다, ~하세요, ~다)를 사용하고 구어체를 쓰지 않습니다."
    ),
    TARGET_PARENT: (
        "학부모 버전: 공손하고 신뢰감 있는 어조를 사용합니다. "
        "안내 중심으로 작성하고 필요 시 협조 요청을 포함할 수 있습니다. "
        "문어체 공지문 문체(예: ~합니다, ~습니다, ~바랍니다)를 사용하고 구어체를 쓰지 않습니다."
    ),
}

PROMPT_VERSION = "v4"


def get_tone_for_target(target):
    return TONE_BY_TARGET.get(target, TONE_CLEAR)


def _get_length_rule(length_style):
    return LENGTH_RULES.get(length_style, LENGTH_RULES[LENGTH_MEDIUM])


def build_system_prompt(selected_target, length_style=LENGTH_MEDIUM):
    target_rule = TARGET_RULES.get(selected_target, TARGET_RULES[TARGET_HIGH])
    length_rule = _get_length_rule(length_style)
    common_rules = (
        "당신은 대한민국 초등학교 담임교사입니다.\n"
        "입력된 대상과 주제에 맞춰 학교에서 바로 사용할 수 있는 멘트를 작성합니다.\n"
        "출력은 문장 본문만 작성합니다.\n\n"
        "[대상 선택 규칙]\n"
        f"- {target_rule}\n\n"
        "[분량 규칙]\n"
        f"- 선택 분량: {length_rule['label']}\n"
        f"- 권장 길이: {length_rule['sentence_range']}, {length_rule['char_range']}\n"
        "- 길이를 맞추기 위해 의미 없는 반복 문장을 넣지 않습니다.\n\n"
        "[문체 고정 규칙]\n"
        "- 모든 대상에서 교사가 작성한 알림장 문어체를 유지합니다.\n"
        "- 문장 종결은 ~합니다, ~습니다, ~하세요, ~바랍니다, ~다 형태를 사용합니다.\n"
        "- 구어체/대화체 표현(예: 거예요, 할 거야, 않을 거야, 해요체 대화문)을 금지합니다.\n\n"
        "[공통 규칙]\n"
        "- 문장 흐름은 도입 -> 핵심 안내 -> 부드러운 당부 순으로 자연스럽게 이어지게 작성합니다.\n"
        "- 문장은 한 단락처럼 읽히도록 자연스럽게 연결합니다.\n"
        "- 같은 종결어미를 반복해서 단조롭게 끝내지 않습니다.\n"
        "- 과도한 이모지, 과장된 표현, 광고성 문장을 쓰지 않습니다.\n"
        "- 구체적 행동 안내를 1개 이상 포함합니다.\n"
        "- 행정문처럼 딱딱한 표현, 번역투, 과한 수식어, 부자연스러운 반복을 피합니다.\n"
        "- 번호 목록, 해시태그, 제목, 인용부호 장식 표현을 금지합니다.\n"
    )

    if selected_target == TARGET_PARENT:
        return (
            common_rules
            + "\n[학부모 전용 규칙]\n"
            "- 학부모가 편안하게 읽을 수 있는 따뜻하고 자연스러운 존댓말을 사용합니다.\n"
            "- 요청/당부 표현은 부담스럽지 않게 완곡하게 조절합니다.\n"
            "\n[최종 점검]\n"
            "- 조건을 만족할 때까지 내부적으로 다듬은 뒤, 최종본 1개만 출력합니다.\n"
            "- 점검 과정, 글자 수, 설명 문구는 출력하지 않습니다.\n"
        )

    return (
        common_rules
        + "\n[학생 전용 보완 규칙]\n"
        "- 학생 눈높이에 맞는 쉬운 낱말을 사용하고 문장을 또렷하게 작성합니다.\n"
        "\n[최종 점검]\n"
        "- 조건을 만족하도록 내부적으로 다듬은 최종본 1개만 출력합니다.\n"
        "- 점검 과정, 설명 문구는 출력하지 않습니다.\n"
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
        "요구사항:\n"
        "- 실제 학교 알림장/주간학습 안내에 바로 붙여넣을 수 있게 작성하세요.\n"
        "- 입력된 핵심 전달사항을 누락하지 마세요.\n"
        "- 행동 안내를 반드시 1개 이상 넣으세요.\n"
        "- 구어체(예: 거예요, 않을 거야, 해요체 대화문) 대신 문어체 공지문으로 작성하세요.\n"
        "- 문장 종결은 ~합니다, ~습니다, ~하세요, ~바랍니다, ~다 형태를 사용하세요.\n"
        "- 문장이 끊겨 보이지 않도록 한 단락처럼 자연스럽게 이어 작성하세요.\n"
        "- 출력은 문장 본문만 제공하고, 부연 설명은 쓰지 마세요.\n"
    )

    if target == TARGET_PARENT:
        prompt += (
            "- 협조 요청 표현은 명령형보다 완곡한 안내형으로 작성하세요.\n"
            "- 선택된 분량 범위를 벗어나면 내부 수정 후 최종본 1개만 출력하세요.\n"
        )

    return prompt
