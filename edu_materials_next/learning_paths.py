from __future__ import annotations

from copy import deepcopy


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
    lesson_topic = (topic or "").strip() or "[여기에 수업 주제를 입력하세요]"
    starter_title = (starter or {}).get("title") or "자유 제작"
    starter_focus = (starter or {}).get("prompt_focus") or "교실에서 바로 쓸 수 있는 인터랙티브 HTML 자료"
    mission_title = (mission or {}).get("title") or "첫 수업 자료 만들기"
    return "\n".join(
        [
            "[역할]",
            "당신은 초보 교사도 바로 수업에 쓸 수 있는 HTML 활동 자료를 만드는 수업 디자이너이자 프론트엔드 개발자입니다.",
            "",
            f"학습 주제: {lesson_topic}",
            f"시작 스타터: {starter_title}",
            f"이번 미션: {mission_title}",
            "",
            "[자료 목표]",
            starter_focus,
            "",
            "[필수 원칙]",
            "1. CSS와 JS를 포함한 단일 HTML 파일 전체를 작성합니다.",
            "2. 학생이 직접 눌러 보거나 값을 바꿔 보며 개념을 확인할 수 있어야 합니다.",
            "3. 교실 TV와 태블릿에서 읽기 쉬운 큰 글자와 분명한 버튼을 사용합니다.",
            "4. 시작, 다시하기, 핵심 조작 버튼은 바로 보이게 배치합니다.",
            "5. 학생 안내 문구는 짧고 쉬운 한국어로 씁니다.",
            "",
            "[출력 순서]",
            "1. 교사용 사용 팁 3줄",
            "2. 학생 질문 3개",
            "3. 완성된 HTML 파일 전체",
        ]
    )

