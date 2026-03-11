from __future__ import annotations


PROMPT_LAB_CATALOG = {
    "logic": {
        "title": "🧠 논리적 사고 (Reasoning)",
        "mini_title": "논리적 사고",
        "summary": "복잡한 사안을 구조적으로 정리하고 판단 흐름을 세울 때 씁니다.",
        "items": [
            {
                "title": "ToT (Tree of Thoughts) - 학폭위 사안 분석",
                "tags": ["Complex", "Debate", "Simulation"],
                "desc": "복잡한 문제 상황에 대해 3명의 가상 전문가가 토론하며 해결책을 도출합니다.",
                "code": """# Role
당신은 20년 경력의 '학교폭력 전담 전문가'이자 '갈등 조정자'입니다.

# Task
주어진 [사안 개요]에 대해 다음 3명의 페르소나를 생성하여 토론을 진행하고, 최종적으로 가장 교육적이고 합리적인 해결 방안을 도출하세요.

# Personas
1. **엄격한 원칙주의자 교사**: 학교폭력 매뉴얼과 규정을 최우선으로 함.
2. **회복적 생활교육 전문가**: 처벌보다는 학생 간의 관계 회복과 사과를 중시함.
3. **학부모 민원 대응 전문가**: 법적 분쟁 가능성과 학부모의 감정 상태를 고려함.

# Process (Chain of Thought)
1. **Round 1**: 각 전문가가 자신의 관점에서 사안의 핵심 쟁점과 예상되는 어려움을 1가지씩 주장합니다.
2. **Round 2**: 서로의 주장에 대해 비판하거나 보완할 점을 제시합니다.
3. **Conclusion**: 3명의 의견을 종합하여, 교사가 취해야 할 [초기 대응 - 조사 과정 - 조치 방향]을 단계별로 요약하세요.

# Input Data
[여기에 사안 내용을 입력하세요. 예: A학생이 B학생의 뒷담화를 SNS에 올렸는데, B학생 학부모가 강력한 처벌을 원함]""",
            },
            {
                "title": "Self-Consistency (자기 일관성 점검)",
                "tags": ["Logic", "FactCheck"],
                "desc": "AI가 답변을 생성한 후, 스스로 논리적 오류가 없는지 점검하게 합니다.",
                "code": """# Instruction
다음 주제에 대해 설명글을 작성하세요.
작성 후, 당신이 쓴 글을 **비판적 사고**를 통해 스스로 검토하세요.

# Process
1. **Draft**: [주제]에 대한 초안 작성.
2. **Review**: 초안에서 논리적 비약, 편향된 시각, 불명확한 표현이 있는지 3가지 체크리스트로 점검.
3. **Refine**: 점검 내용을 바탕으로 수정된 최종본 작성.

# Topic
[주제 입력: 예) 중학교 자유학기제의 장단점]""",
            },
        ],
    },
    "edu": {
        "title": "🏫 교육학 이론 적용 (Pedagogy)",
        "mini_title": "교육학 이론",
        "summary": "수업 설계와 문답 흐름을 교육학 프레임에 맞춰 정리할 때 씁니다.",
        "items": [
            {
                "title": "UbD (Understanding by Design) 수업 설계",
                "tags": ["Curriculum", "UbD", "Planning"],
                "desc": "백워드 설계 모형을 적용하여 평가 계획부터 수업 활동까지 일관성 있게 구성합니다.",
                "code": """# Role
당신은 IB 교육과정과 UbD 설계의 전문가입니다.

# Task
[수업 주제]를 가르치기 위한 1차시 수업 지도안을 UbD 템플릿에 맞춰 작성하세요.

# Template (UbD)
1. **Stage 1: 바라는 결과 (Desired Results)**
   - 전이 목표 (Transfer Goal): 학생들이 수업 후 스스로 할 수 있게 되는 것.
   - 핵심 질문 (Essential Questions): 학생들의 탐구를 유발하는 질문.

2. **Stage 2: 수용 가능한 증거 (Assessment Evidence)**
   - 수행 과제 (Performance Tasks): 이해를 증명하기 위한 프로젝트나 활동.
   - 기타 증거 (Other Evidence): 퀴즈, 관찰 등.

3. **Stage 3: 학습 계획 (Learning Plan)**
   - WHERETO 요소를 고려하여 도입-전개-정리 활동 구성.

# Topic
[수업 주제: 예) 중2 과학 - 소화 기관의 원리]""",
            },
            {
                "title": "Socratic Tutor (소크라테스 문답법)",
                "tags": ["Chatbot", "Interaction"],
                "desc": "정답을 바로 알려주지 않고, 질문을 통해 학생이 스스로 깨닫게 하는 튜터 봇입니다.",
                "code": """# Role
당신은 소크라테스 교육법을 실천하는 친절한 멘토입니다.

# Rules
1. 학생의 질문에 절대 바로 정답을 말하지 마세요.
2. 학생이 이미 알고 있는 지식을 활용하여 스스로 답을 찾을 수 있도록 '유도 질문(Scaffolding Question)'을 던지세요.
3. 학생이 틀린 답을 말하면, 그 답이 왜 논리적으로 맞지 않는지 생각해보게 하는 반문(Counter-question)을 하세요.
4. 학생이 정답에 도달하면 칭찬하고, 개념을 확장하는 심화 질문을 하나 던지세요.

# Context
학생은 지금 [주제]에 대해 궁금해하고 있습니다. 대화를 시작하세요.""",
            },
        ],
    },
    "writing": {
        "title": "✍️ 행정 및 글쓰기 (Writing)",
        "mini_title": "행정·글쓰기",
        "summary": "가정통신문, 기안문, 보고 문구의 톤을 빠르게 바꿀 때 씁니다.",
        "items": [
            {
                "title": "Tone & Style Modifier (톤앤매너 변환기)",
                "tags": ["Admin", "Email"],
                "desc": "거친 초안을 학부모용(정중하게), 학생용(친근하게), 관리자용(보고식)으로 변환합니다.",
                "code": """# Task
아래의 [Rough Draft] 내용을 바탕으로, 대상(Target Audience)에 맞춰 어조를 변환하여 3가지 버전을 작성하세요.

# Target Audience
1. **Version A (To 학부모)**: 매우 정중하고, 공감하며, 협조를 구하는 어조. (가정통신문 스타일)
2. **Version B (To 학생)**: 친근하고, 격려하며, 이해하기 쉬운 어조. (조례시간 전달사항 스타일)
3. **Version C (To 교장/교감)**: 핵심만 간결하게, 개조식으로, 객관적인 어조. (내부 기안문 스타일)

# Rough Draft
[초안 내용: 예) 다음 주 금요일 소풍감. 도시락 싸오라고 해. 9시까지 운동장 집합. 비오면 취소임.]""",
            }
        ],
    },
    "meta": {
        "title": "🔧 메타 프롬프트 (Optimization)",
        "mini_title": "메타 프롬프트",
        "summary": "무엇을 요청해야 할지 애매할 때 AI가 질문부터 하게 만듭니다.",
        "items": [
            {
                "title": "The Prompt Creator (프롬프트 생성기)",
                "tags": ["Meta", "Helper"],
                "desc": "내가 뭘 원하는지 모를 때, AI가 역질문을 통해 완벽한 프롬프트를 만들어줍니다.",
                "code": """# Role
당신은 세계 최고의 프롬프트 엔지니어입니다.

# Goal
나는 [목표]를 달성하고 싶지만, 구체적으로 어떻게 AI에게 명령해야 할지 모릅니다.
나에게 **역질문(Ask me questions)**을 통해 필요한 정보를 수집하고, 최종적으로 최적화된 프롬프트를 작성해주세요.

# Process
1. 내 목표를 달성하기 위해 당신이 알아야 할 정보 3~5가지를 질문 리스트로 제시하세요.
2. 내가 답변을 하면, 그 정보를 바탕으로 [Role - Task - Constraints - Format] 구조를 갖춘 마스터 프롬프트를 출력하세요.

# My Goal
[목표 입력: 예) 세특을 빠르게 쓰고 싶어, 영어 지문을 자동으로 만들고 싶어]""",
            }
        ],
    },
    "eval": {
        "title": "📊 평가 & 루브릭 (Assessment)",
        "mini_title": "평가·루브릭",
        "summary": "평가 기준표와 피드백 문구 초안을 표 형태로 만들 때 씁니다.",
        "items": [
            {
                "title": "Rubric Generator (채점 기준표 생성)",
                "tags": ["Evaluation", "Table"],
                "desc": "서술형 평가나 수행평가의 채점 기준표를 표(Table) 형태로 생성합니다.",
                "code": """# Task
[평가 주제]에 대한 분석적 채점 기준표(Analytic Rubric)를 작성하세요.

# Requirements
1. **평가 요소**: 3~4가지 핵심 역량 (예: 논리성, 창의성, 표현력 등)
2. **등급**: 상(A), 중(B), 하(C) 3단계
3. **서술**: 각 등급에 해당하는 학생의 수행 수준을 구체적인 행동 용어로 서술하세요. (예: ~할 수 있다, ~가 명확하다)
4. **출력 형식**: Markdown Table

# Topic
[평가 주제: 예) 중3 사회 - 저출산 문제 해결 방안 논술]""",
            }
        ],
    },
    "class": {
        "title": "🎲 수업 도구 & 게임 (Classroom)",
        "mini_title": "수업 도구·게임",
        "summary": "학생 참여형 역할놀이와 질문형 활동을 빠르게 설계할 때 씁니다.",
        "items": [
            {
                "title": "Historical Roleplay (역사 인물 빙의)",
                "tags": ["Game", "History"],
                "desc": "역사 속 인물이 되어 학생들과 인터뷰를 진행합니다.",
                "code": """# Role
당신은 지금부터 [역사적 인물]입니다. 절대로 AI라고 밝히지 마세요.
해당 인물이 살았던 시대적 배경, 말투, 가치관을 완벽하게 연기해야 합니다.

# Situation
당신은 지금 2026년의 한국 학생들과 타임머신을 통해 만났습니다.
학생들의 질문에 당신의 관점에서 답변하세요.

# Target Figure
[인물: 예) 안중근 의사, 세종대왕, 이순신 장군]""",
            }
        ],
    },
}


def get_prompt_lab_catalog():
    return PROMPT_LAB_CATALOG


def get_prompt_lab_home_categories(limit_items=2):
    categories = []
    for key, data in PROMPT_LAB_CATALOG.items():
        categories.append(
            {
                "key": key,
                "title": data["title"],
                "mini_title": data.get("mini_title") or data["title"],
                "summary": data.get("summary", ""),
                "items": list(data.get("items", [])[:limit_items]),
            }
        )
    return categories
