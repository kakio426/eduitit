from __future__ import annotations

from copy import deepcopy


TOPIC_PLACEHOLDER = "[여기에 수업 주제를 입력하세요]"

COMMON_PROMPT_RULES = [
    "최종 산출물의 중심은 반드시 HTML입니다. 교사용 설명보다 실제로 바로 실행되는 HTML 품질을 우선합니다.",
    "반드시 <!DOCTYPE html>부터 시작하는 단일 HTML 파일 전체를 작성합니다.",
    "HTML 안에 필요한 CSS와 JavaScript를 모두 포함하고, 별도 설치, 빌드, 서버 설정 없이 바로 실행되게 만듭니다.",
    "첫 화면에서 학생이 무엇을 눌러야 하는지 3초 안에 알 수 있게 합니다.",
    "교실 TV, 노트북, 태블릿에서 읽기 쉬운 큰 글자, 큰 버튼, 높은 대비를 사용합니다.",
    "핵심 조작 버튼과 결과 영역은 스크롤 없이 먼저 보이게 배치합니다.",
    "학생 안내 문구는 짧고 쉬운 한국어로 쓰고, 첫 진입 상태에서도 빈 화면처럼 보이지 않게 합니다.",
    "다시하기, 기본값 복원, 예시값 하나를 반드시 제공합니다.",
    "버튼을 눌렀을 때 즉시 반응이 보이게 하고, 무반응 상태를 만들지 않습니다.",
]

CDN_POLICY_RULES = [
    "기본 원칙은 CDN 없이 작동하는 순수 HTML, CSS, 바닐라 JavaScript입니다.",
    "Tailwind CDN, 외부 폰트, 외부 이미지, 외부 오디오, npm import, ES module CDN import는 사용하지 않습니다.",
    "시각화와 애니메이션은 가능한 한 SVG, Canvas, CSS, 기본 DOM API로 해결합니다.",
    "정말 불가피할 때만 검증된 외부 라이브러리 1개를 제한적으로 쓸 수 있지만, 특별한 이유가 없다면 CDN 없는 구현을 우선합니다.",
    "외부 리소스를 쓰더라도 핵심 학습 흐름이 멈추거나 흰 화면이 되지 않게 대체 UI 또는 기본 동작을 남깁니다.",
]

QUALITY_CHECKLIST = [
    "예시 데이터나 기본 상태만으로도 바로 시연할 수 있어야 합니다.",
    "학생 조작 -> 화면 변화 -> 해석 포인트가 자연스럽게 이어져야 합니다.",
    "장식용 모션보다 개념 이해와 조작 피드백이 더 중요합니다.",
    "설명 문단을 길게 늘어놓기보다 화면 구조와 버튼 배치만으로 사용법이 보이게 합니다.",
    "교사가 수업 직전에 열어도 당황하지 않도록 제목, 안내, 조작, 결과가 한 화면에서 정리되어야 합니다.",
]

OUTPUT_REQUIREMENTS = [
    "먼저 교사용 사용 팁 3줄을 제공합니다.",
    "다음으로 학생 질문 3개를 제공합니다.",
    "마지막에 순수 HTML만 제공합니다. HTML 부분은 코드블록 없이 <!DOCTYPE html>부터 끝까지 이어서 작성합니다.",
    "HTML 바깥 설명은 최소화하고, HTML 안에 백틱이나 마크다운 표기를 넣지 않습니다.",
]

MATERIAL_TYPE_GUIDANCE = {
    "intro": {
        "label": "도입형 자료",
        "goal": "새 개념을 짧은 시간 안에 직관적으로 붙잡게 하는 도입형 수업 자료",
        "lines": [
            "첫 1분 안에 학생의 시선을 끄는 핵심 장면이나 질문을 보여 줍니다.",
            "조작은 1~2개만 두고, 개념 하나에 집중합니다.",
            "짧은 예측 질문이나 빠른 확인 활동을 넣어 도입이 끝나자마자 반응을 끌어냅니다.",
            "복잡한 설정 패널이나 긴 설명 카드로 시작하지 않습니다.",
        ],
    },
    "exploration": {
        "label": "탐구형 자료",
        "goal": "학생이 값을 조작하고 결과 변화를 관찰하며 스스로 규칙을 찾게 하는 탐구형 자료",
        "lines": [
            "학생이 직접 바꿀 핵심 변수 2~3개를 제공하고, 값이 바뀌면 결과가 즉시 눈에 보이게 합니다.",
            "현재 값, 변화 결과, 비교 포인트를 한눈에 볼 수 있는 관찰 영역을 둡니다.",
            "기본값, 다시하기, 비교용 preset을 제공합니다.",
            "단순 재생형 애니메이션으로 끝내지 말고 학생 조작이 결과를 바꾸게 만듭니다.",
        ],
    },
    "practice": {
        "label": "연습형 자료",
        "goal": "짧은 반복과 즉시 피드백으로 개념을 확인하는 연습형 자료",
        "lines": [
            "학생이 여러 번 시도할 수 있도록 문제를 반복 가능한 구조로 만듭니다.",
            "정답 여부만 보여 주지 말고 왜 그런지 짧은 힌트나 비교 설명을 함께 제공합니다.",
            "즉시 피드백, 다시 도전, 다음 문제 흐름을 끊김 없이 이어 줍니다.",
            "정적인 문제지처럼 보이지 않게 시각 표현이나 조작 요소를 반드시 넣습니다.",
        ],
    },
    "quiz": {
        "label": "퀴즈형 자료",
        "goal": "짧은 문항을 빠르게 풀며 학습 상태를 확인하는 퀴즈형 자료",
        "lines": [
            "질문 수, 현재 진행 상태, 점수 또는 맞힌 개수를 분명히 보여 줍니다.",
            "문항은 짧고 명확하게 쓰고, 한 화면에서 다음 행동이 바로 보여야 합니다.",
            "마지막에는 결과 요약과 다시하기를 제공합니다.",
            "함정형 문제나 긴 지문 위주의 테스트로 만들지 않습니다.",
        ],
    },
    "game": {
        "label": "게임형 자료",
        "goal": "학습 목표를 유지한 채 짧은 도전과 보상으로 몰입을 만드는 게임형 자료",
        "lines": [
            "학생이 무엇을 하면 성공인지 규칙과 목표를 한눈에 이해할 수 있게 합니다.",
            "점수, 남은 기회, 단계 변화 등 게임 상태를 분명히 보여 줍니다.",
            "게임 요소는 개념 이해를 돕는 수단이어야 하며, 랜덤 효과가 학습 목표를 가리면 안 됩니다.",
            "한 판이 3~5분 안에 끝나고 다시 도전하기 쉬워야 합니다.",
        ],
    },
    "reference": {
        "label": "참고자료형 자료",
        "goal": "학생과 교사가 빠르게 찾아보고 비교할 수 있는 정리형 자료",
        "lines": [
            "카드, 탭, 아코디언, 필터 중 한 가지를 써서 정보를 짧게 나눠 보여 줍니다.",
            "핵심 예시와 비교 포인트를 함께 두어 읽기만 하는 자료가 되지 않게 합니다.",
            "긴 스크롤 텍스트 벽 대신 작은 묶음으로 나눠 탐색 가능하게 만듭니다.",
            "교실 화면에서 제목과 핵심 키워드가 멀리서도 읽히게 합니다.",
        ],
    },
    "presentation": {
        "label": "발표형 자료",
        "goal": "학생 발표, 주장 정리, 토론 공유에 바로 쓰는 발표형 자료",
        "lines": [
            "전자칠판이나 빔 화면에서 잘 보이도록 큰 타이포와 넓은 여백을 사용합니다.",
            "학생이 주장, 근거, 예시, 질문을 빠르게 채우거나 정리할 수 있게 합니다.",
            "발표 전에 생각을 구조화하는 칸과 발표 중 보여 줄 핵심 화면을 명확히 구분합니다.",
            "복잡한 문서 편집기처럼 만들지 말고 발표 흐름에 필요한 입력만 남깁니다.",
        ],
    },
    "tool": {
        "label": "도구형 자료",
        "goal": "입력값을 넣으면 결과가 바로 계산되거나 시각화되는 교실용 도구",
        "lines": [
            "입력 영역, 결과 영역, 예시값, 초기화 버튼을 명확히 나눕니다.",
            "입력값이 바뀌면 결과가 즉시 바뀌어야 하고, 계산 과정이나 기준을 짧게 보여 줍니다.",
            "교사와 학생이 모두 쓸 수 있도록 라벨과 단위를 분명히 씁니다.",
            "숨겨진 규칙이나 애매한 입력 방식 없이 바로 실험 가능한 도구로 만듭니다.",
        ],
    },
    "other": {
        "label": "일반형 자료",
        "goal": "교실에서 바로 쓸 수 있는 인터랙티브 HTML 자료",
        "lines": [
            "한 화면에서 핵심 목표 하나에 집중합니다.",
            "학생 조작과 즉시 반응을 반드시 포함합니다.",
            "교사가 설명하지 않아도 첫 행동이 보이게 구성합니다.",
        ],
    },
}

SUBJECT_GUIDANCE = {
    "SCIENCE": [
        "과학 개념은 단순 장식이 아니라 변수 변화와 결과의 인과 관계가 보이게 합니다.",
        "값의 크기나 변화는 가능한 한 현실적인 범위나 학습용 합리적 범위를 사용합니다.",
        "관찰 포인트를 화면에서 바로 읽을 수 있게 라벨과 수치를 제공합니다.",
    ],
    "MATH": [
        "수학 개념은 숫자, 도형, 막대, 수직선, 표 등 시각 표현과 연결합니다.",
        "정답만 보여 주지 말고 왜 그런지 비교 근거가 눈에 보이게 합니다.",
        "학생이 숫자를 바꾸면 규칙이 어떻게 변하는지 즉시 확인할 수 있어야 합니다.",
    ],
    "KOREAN": [
        "국어 자료는 문장 틀, 주장과 근거, 핵심어 정리 등 언어적 발판을 제공합니다.",
        "입력 칸이 있다면 너무 길게 쓰지 않아도 되도록 짧은 문장 중심으로 설계합니다.",
        "읽기 자료는 긴 본문보다 핵심 문장과 구조를 빠르게 파악하게 돕는 방식으로 제시합니다.",
    ],
    "SOCIAL": [
        "사회 자료는 관점 비교, 시간 흐름, 사례 비교 같은 구조를 분명히 보여 줍니다.",
        "의견과 근거가 구분되게 하고, 학생이 판단 이유를 말할 수 있게 돕습니다.",
        "지도나 연표가 꼭 필요하지 않다면 기본 카드와 비교 영역만으로도 충분히 설명되게 만듭니다.",
    ],
    "OTHER": [
        "낯선 주제라도 학생이 바로 이해할 수 있도록 예시를 먼저 보여 줍니다.",
        "전문 용어는 최소화하고 필요한 경우 짧은 설명을 함께 둡니다.",
    ],
}

MISSION_GUIDANCE = {
    "vibe-basics": [
        "처음 만드는 자료이므로 한 화면 안에서 끝나는 단순한 구조를 우선합니다.",
        "핵심 조작은 1~2개만 두고, 처음 본 교사도 바로 시연할 수 있게 만듭니다.",
    ],
    "interactive-lesson": [
        "학생이 조작하고 관찰한 뒤 말로 설명하게 되는 탐구 흐름을 화면 안에 넣습니다.",
        "변수 조작과 관찰 포인트를 분명히 연결합니다.",
    ],
    "quick-practice": [
        "수업 마지막 5분에도 바로 쓸 수 있도록 빠른 시작과 즉시 피드백을 우선합니다.",
        "문제 풀이 흐름이 길어지지 않게 한 번에 한 과제씩 보여 줍니다.",
    ],
    "discussion-flow": [
        "학생이 생각을 정리하고 발표로 이어 가는 흐름을 도와야 합니다.",
        "주장, 근거, 반대 의견, 마무리 생각을 구조적으로 채울 수 있게 합니다.",
    ],
}

STARTER_LIBRARY = [
    {
        "slug": "planet-lab",
        "title": "행성 운동 관찰실",
        "summary": "행성의 자전과 공전을 직접 움직여 보며 비교하는 탐구형 자료",
        "subject": "SCIENCE",
        "grade": "5학년 1학기",
        "unit_title": "태양계와 별",
        "material_type": "exploration",
        "estimated_minutes": 15,
        "difficulty_level": "beginner",
        "teacher_guide": "행성을 하나씩 켜 보게 하고, 공전 주기와 자전 속도를 바꿔 보게 하세요.",
        "student_questions": [
            "어느 행성이 가장 빠르게 한 바퀴 도나요?",
            "속도를 바꾸면 화면에서 어떤 차이가 보이나요?",
            "지구와 다른 행성의 낮과 1년 길이는 어떻게 다를까요?",
        ],
        "remix_tips": [
            "행성 수를 3개만 남겨 비교형으로 줄이기",
            "속도 조절 슬라이더를 더 크게 키우기",
            "학생 발표용 설명 박스를 아래쪽에 추가하기",
        ],
        "prompt_focus": "행성의 움직임을 조작하며 비교하는 실험형 인터랙티브 HTML 자료",
        "prompt_requirements": [
            "행성이나 천체가 실제로 움직이는 중심 시각화 영역을 둡니다.",
            "자전, 공전, 속도 비교처럼 학생이 바꿔 볼 수 있는 조작 2개 이상을 제공합니다.",
            "현재 선택한 행성의 상태나 관찰 포인트를 보여 주는 작은 대시보드를 둡니다.",
        ],
        "prompt_quality_checks": [
            "행성별 차이가 화면에서 분명히 느껴져야 합니다.",
            "단순 GIF처럼 자동 재생만 되는 화면이 아니라 학생 조작이 결과를 바꾸어야 합니다.",
        ],
    },
    {
        "slug": "fraction-balance",
        "title": "분수 크기 비교 실험판",
        "summary": "분모와 분자를 바꿔 보며 분수의 크기를 직관적으로 확인하는 수학 자료",
        "subject": "MATH",
        "grade": "4학년 2학기",
        "unit_title": "분수의 크기 비교",
        "material_type": "practice",
        "estimated_minutes": 12,
        "difficulty_level": "beginner",
        "teacher_guide": "학생이 직접 수를 바꾸어 보고, 어떤 경우에 막대 길이가 같아지는지 말하게 하세요.",
        "student_questions": [
            "분모가 커지면 막대 길이는 어떻게 달라지나요?",
            "같은 크기의 분수는 어떤 규칙이 있나요?",
            "1보다 큰 분수는 화면에서 어떻게 보이나요?",
        ],
        "remix_tips": [
            "막대 대신 피자 조각 그림으로 바꾸기",
            "퀴즈 버튼을 추가해 즉시 확인형으로 바꾸기",
            "학급별 예시 숫자를 기본값으로 바꾸기",
        ],
        "prompt_focus": "분수의 크기를 시각적으로 비교하고 학생이 값을 바꿔 볼 수 있는 인터랙티브 HTML 자료",
        "prompt_requirements": [
            "두 분수를 나란히 비교할 수 있는 시각 영역을 둡니다.",
            "분자와 분모를 바로 바꿔 볼 수 있는 입력 또는 버튼을 제공합니다.",
            "같다, 크다, 작다 같은 비교 결과를 짧은 문장으로 즉시 보여 줍니다.",
        ],
        "prompt_quality_checks": [
            "분수 막대나 도형이 학생 눈에 직관적으로 보이게 해야 합니다.",
            "1보다 큰 분수나 같은 크기의 분수도 자연스럽게 표현되어야 합니다.",
        ],
    },
    {
        "slug": "volcano-lab",
        "title": "화산 활동 시뮬레이션",
        "summary": "압력과 분출 강도를 조절하며 화산 활동을 이해하는 과학 자료",
        "subject": "SCIENCE",
        "grade": "4학년 1학기",
        "unit_title": "화산과 지진",
        "material_type": "game",
        "estimated_minutes": 15,
        "difficulty_level": "intermediate",
        "teacher_guide": "분출 전 압력을 먼저 예상하게 하고, 실험 뒤 실제 분출 결과를 비교하게 하세요.",
        "student_questions": [
            "압력이 높아질수록 어떤 변화가 보이나요?",
            "안전하게 분출을 줄이려면 어떤 값을 바꿔야 하나요?",
            "실제 화산과 비슷한 점과 다른 점은 무엇인가요?",
        ],
        "remix_tips": [
            "버튼 수를 줄여 저학년용으로 단순화하기",
            "정리 질문을 카드 형태로 화면 아래 추가하기",
            "지진 진동 요소를 더해 확장형 자료로 바꾸기",
        ],
        "prompt_focus": "압력과 분출 세기를 조절하며 화산 활동을 이해하는 인터랙티브 HTML 시뮬레이션",
        "prompt_requirements": [
            "압력, 점성, 분출 강도처럼 결과를 바꾸는 조작값을 분명히 보여 줍니다.",
            "화산 상태가 한눈에 보이는 시각 영역과 안전/위험 피드백을 제공합니다.",
            "게임처럼 도전할 수 있는 목표나 점수 또는 성공 조건을 짧게 넣습니다.",
        ],
        "prompt_quality_checks": [
            "화려한 효과보다 압력 변화와 분출 결과의 연결이 더 분명해야 합니다.",
            "다시하기 한 번으로 바로 새 실험을 시작할 수 있어야 합니다.",
        ],
    },
    {
        "slug": "debate-canvas",
        "title": "찬반 토론 정리판",
        "summary": "학생이 주장과 근거를 채우며 토론 구조를 정리하는 발표형 자료",
        "subject": "KOREAN",
        "grade": "6학년 1학기",
        "unit_title": "주장과 근거",
        "material_type": "presentation",
        "estimated_minutes": 20,
        "difficulty_level": "beginner",
        "teacher_guide": "쟁점 하나를 제시한 뒤, 주장과 근거를 두 칸에 나눠 정리하게 하세요.",
        "student_questions": [
            "내 주장에 가장 강한 근거는 무엇인가요?",
            "반대 의견은 어떤 근거를 들 수 있나요?",
            "토론 뒤 내 생각이 바뀌었나요?",
        ],
        "remix_tips": [
            "사회 과목 논쟁 주제로 바꾸기",
            "근거 카드 수를 2개에서 4개로 늘리기",
            "발표 순서를 뽑는 버튼을 추가하기",
        ],
        "prompt_focus": "학생이 주장과 근거를 정리하고 발표할 수 있는 토론용 인터랙티브 HTML 자료",
        "prompt_requirements": [
            "주장, 근거, 반대 의견을 구분해 적거나 배치할 수 있는 칸을 둡니다.",
            "발표할 때도 잘 보이도록 큰 제목과 큰 카드 중심으로 구성합니다.",
            "학생이 완전히 빈칸에서 시작하지 않도록 문장 틀이나 예시 문구를 제공합니다.",
        ],
        "prompt_quality_checks": [
            "문서 편집기처럼 복잡하면 안 되고, 발표 직전 바로 정리 가능한 수준이어야 합니다.",
            "교실 전면 화면에서 멀리서도 카드 제목과 핵심 문장이 보여야 합니다.",
        ],
    },
]

MISSION_LIBRARY = [
    {
        "slug": "vibe-basics",
        "title": "바이브코딩 처음",
        "summary": "스타터 하나를 고르고 AI로 첫 HTML 수업자료를 만드는 입문 미션",
        "starter_slug": "planet-lab",
        "first_step": "주제를 한 문장으로 적고 스타터를 그대로 따라 해 보세요.",
    },
    {
        "slug": "interactive-lesson",
        "title": "탐구형 자료 만들기",
        "summary": "학생이 직접 값을 조작하는 탐구형 인터랙티브 자료를 만드는 미션",
        "starter_slug": "volcano-lab",
        "first_step": "학생이 무엇을 조작할지 하나만 먼저 정하세요.",
    },
    {
        "slug": "quick-practice",
        "title": "복습형 자료 만들기",
        "summary": "짧은 복습과 확인 활동에 쓰는 인터랙티브 연습 자료를 만드는 미션",
        "starter_slug": "fraction-balance",
        "first_step": "수업 마지막 5분에 확인하고 싶은 개념 하나를 고르세요.",
    },
    {
        "slug": "discussion-flow",
        "title": "발표형 자료 만들기",
        "summary": "학생 발표나 찬반 토론에 바로 쓰는 발표형 자료를 만드는 미션",
        "starter_slug": "debate-canvas",
        "first_step": "발표 전에 학생이 꼭 남겨야 할 생각 칸 2개를 정하세요.",
    },
]


def _section(title: str, lines: list[str]) -> list[str]:
    return [f"[{title}]"] + [f"- {line}" for line in lines] + [""]


def get_starter(slug: str):
    for starter in STARTER_LIBRARY:
        if starter["slug"] == slug:
            return deepcopy(starter)
    return None


def get_mission(slug: str):
    for mission in MISSION_LIBRARY:
        if mission["slug"] == slug:
            return deepcopy(mission)
    return None


def build_ai_prompt(topic: str, *, starter=None, mission=None) -> str:
    lesson_topic = (topic or "").strip() or TOPIC_PLACEHOLDER
    starter = deepcopy(starter) if starter else None
    mission = deepcopy(mission) if mission else None

    if not starter and mission and mission.get("starter_slug"):
        starter = get_starter(mission["starter_slug"])

    material_type = (starter or {}).get("material_type") or "other"
    subject = (starter or {}).get("subject") or "OTHER"
    material_guidance = MATERIAL_TYPE_GUIDANCE.get(material_type, MATERIAL_TYPE_GUIDANCE["other"])
    subject_guidance = SUBJECT_GUIDANCE.get(subject, SUBJECT_GUIDANCE["OTHER"])
    mission_guidance = MISSION_GUIDANCE.get((mission or {}).get("slug", ""), [])

    starter_title = (starter or {}).get("title") or "자유 제작"
    starter_focus = (starter or {}).get("prompt_focus") or "교실에서 바로 쓸 수 있는 인터랙티브 HTML 자료"
    mission_title = (mission or {}).get("title") or "첫 수업 자료 만들기"
    mission_first_step = (mission or {}).get("first_step") or "학생이 무엇을 눌러 보고 어떤 반응을 봐야 하는지 먼저 정합니다."

    prompt_lines = [
        "[역할]",
        "당신은 초보 교사도 설명 없이 바로 수업에 쓸 수 있는 HTML 활동 자료를 만드는 수업 디자이너이자 프론트엔드 개발자입니다.",
        "",
        "[수업 맥락]",
        f"- 학습 주제: {lesson_topic}",
        f"- 자료 유형: {material_guidance['label']}",
        f"- 시작 스타터: {starter_title}",
        f"- 이번 미션: {mission_title}",
        "",
        "[이번 자료의 핵심 목표]",
        f"- {starter_focus}",
        f"- 미션 첫걸음: {mission_first_step}",
        "",
    ]
    prompt_lines += _section("공통 HTML 제작 원칙", COMMON_PROMPT_RULES)
    prompt_lines += _section("CDN 및 외부 리소스 규칙", CDN_POLICY_RULES)
    prompt_lines += _section(
        "자료 유형별 설계",
        [material_guidance["goal"], *material_guidance["lines"]],
    )
    prompt_lines += _section("과목 특화 포인트", subject_guidance)
    if mission_guidance:
        prompt_lines += _section("이번 미션에서 더 강조할 점", mission_guidance)
    if starter:
        prompt_lines += _section(
            "이 스타터에서 꼭 살아야 할 요소",
            list((starter or {}).get("prompt_requirements", [])),
        )
        prompt_lines += _section(
            "스타터 품질 체크",
            list((starter or {}).get("prompt_quality_checks", [])),
        )
    prompt_lines += _section("완성 품질 체크", QUALITY_CHECKLIST)
    prompt_lines += _section("출력 형식", OUTPUT_REQUIREMENTS)
    return "\n".join(prompt_lines).strip()
