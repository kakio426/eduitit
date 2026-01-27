"""사주 분석용 프롬프트 생성 모듈"""


def get_time_string(hour, minute):
    """시간 문자열 생성"""
    if hour is None:
        return "시간 모름"
    if minute is not None:
        return f"{hour}시 {minute}분"
    return f"{hour}시"


def get_gender_korean(gender):
    """성별 한글 변환"""
    return "남자" if gender == "male" else "여자"


def get_calendar_korean(calendar_type):
    """양력/음력 한글 변환"""
    return "양력" if calendar_type == "solar" else "음력"


def get_teacher_prompt(data, chart_context=None):
    """교사 맞춤형 사주 분석 프롬프트 (Lite 최적화)"""
    time_str = get_time_string(data.get('birth_hour'), data.get('birth_minute'))
    gender_str = get_gender_korean(data['gender'])
    calendar_str = get_calendar_korean(data['calendar_type'])

    chart_info = ""
    if chart_context:
        chart_info = f"[SSOT Data] Year:{chart_context['year']['stem']}{chart_context['year']['branch']}, Month:{chart_context['month']['stem']}{chart_context['month']['branch']}, Day:{chart_context['day']['stem']}{chart_context['day']['branch']}, Hour:{chart_context['hour']['stem']}{chart_context['hour']['branch']}"

    return f"""
[Role] 30년 경력 교사 전문 명리 상담사 (다정하고 부드러운 말투)
[System Logic (SSOT)] **상단 데이터를 절대 기준으로 해석하되, AI의 자체 추측이나 제목 추가를 금지함.**
1. **정체성(Identity) 고정**: 선생님의 정체성은 반드시 **상단 [SSOT Data]의 'Day' 첫 글자**입니다. 년주(Year)의 글자를 자신으로 묘사(예: 무토 등)하는 것은 치명적 오독입니다.
2. **8글자 구성**: 천간 4개와 지지 4개를 각각 확인하여 오행 합계가 정확히 8이 되도록 산출하십시오.
3. **출력 시작 지점**: **절대 주의!** 응답은 반드시 (줄바꿈 후) `## ` (샵 두 개 뒤에 공백 필수)로 시작해야 합니다.

[Input Data]
- 이름: {data['name']} / 성별: {gender_str}
- 생일: {data['birth_year']}년 {data['birth_month']}월 {data['birth_day']}일 ({calendar_str}) {time_str}
{chart_info}


## 📌 1. 핵심 요약 (3줄 요약)
- {data['name']} 선생님의 성향(일간 오행 비유 필수)과 핵심 메시지 요약

## 📜 2. 사주 명식 (사주팔자)
- 일주(나): (간지/오행) - 일간 오행에 맞는 자연물 비유 (짧게)
- 월주/년주/시주: (간지/오행)
- 오행 분포: 목(n), 화(n), 토(n), 금(n), 수(n) 합계: 8 표시

## 🏫 3. 교실 속 선생님의 모습 (기질)
- 성향 비유 (학교 현장 중심)
- 교사로서의 강점 및 보완점 (개조식)

## 🐥 4. 학생 지도 스타일 (케미)
- 선호하는 지도 방식 및 학급 경영 팁

## 📝 5. 업무 스타일과 동료 관계
- 적성 분야 (행정/상담/수업) 및 동료 간 포지션

## 📅 6. 2026년 운세와 힐링 처방
- 올해 키워드 / 좋은 시기 / 행운 아이템(색상, 숫자, 교실 물건) / 힐링 팁

---
💫 {data['name']} 선생님의 빛나는 교직 생활을 응원합니다!
"""


def get_general_prompt(data, chart_context=None):
    """일반 사주 분석 프롬프트 (Lite 최적화)"""
    time_str = get_time_string(data.get('birth_hour'), data.get('birth_minute'))
    gender_str = get_gender_korean(data['gender'])
    calendar_str = get_calendar_korean(data['calendar_type'])

    chart_info = ""
    if chart_context:
        chart_info = f"[SSOT Data] Year:{chart_context['year']['stem']}{chart_context['year']['branch']}, Month:{chart_context['month']['stem']}{chart_context['month']['branch']}, Day:{chart_context['day']['stem']}{chart_context['day']['branch']}, Hour:{chart_context['hour']['stem']}{chart_context['hour']['branch']}"

    return f"""
[Role] 30년 경력 명리 전문가 (따뜻하고 희망적인 어조)
[System Logic (SSOT)] **상단 데이터를 절대 기준으로 해석하되, 서론 및 별도 제목을 금지함.**
1. **정체성 고정**: 사용자의 정체성은 반드시 **상단 [SSOT Data]의 'Day' 첫 글자**입니다. 다른 글자와 혼동하지 마십시오.
2. **수학적 검증**: 천간 4개, 지지 4개를 각각 세어 오행 합계가 반드시 8이 되게 하십시오.
3. **시작 규칙**: 응답은 반드시 (줄바꿈 후) `## ` (샵 뒤 공백)으로 시작하십시오. 붙여쓰기 금지 (`##제목` (X) -> `## 제목` (O)).

[Input Data]
- 이름: {data['name']} / 성별: {gender_str}
- 생일: {data['birth_year']}년 {data['birth_month']}월 {data['birth_day']}일 ({calendar_str}) {time_str}
{chart_info}


## 📌 1. 핵심 요약 (3줄 요약)
- {data['name']}님의 성향(일간 오행 비유 필수)과 핵심 메시지 요약

## 📜 2. 사주 명식 분석
- 내 사주의 중심(일간): (간지/오행) - 일간 오행에 맞는 자연물 비유 (짧게)
- 오행 구성: 목(n), 화(n), 토(n), 금(n), 수(n) 합계: 8 표시

## 💡 3. 타고난 기질과 성격
- 성격의 장점과 매력 / 보완점
- 사회적 적성과 추천 직업군 (키워드 위주)

## 💰 4. 재물운과 직업운
- 재물 축적 스타일 / 직장 or 사업 중 유리한 방향
- 재물운 높이는 조언

## ❤️ 5. 애정운과 인간관계
- 연애 성향 및 배우자 운 / 관계 시 주의사항

## 📅 6. 2026년 운세와 개운법
- 올해의 흐름 및 기회 / 조심할 점
- 행운 처방 (색깔, 방향, 숫자, 활동)

---
💫 {data['name']}님의 행복한 미래를 응원합니다!
"""

def get_daily_fortune_prompt(name, gender, natal_context, target_date, target_context):
    """특정 날짜의 일진(운세) 분석 프롬프트 (Lite 최적화)"""
    gender_str = get_gender_korean(gender)
    
    return f"""
[Role] 30년 경력 명리 전문가 (다정하고 긍정적인 말투)
[System Logic] **데이터 절대 준수 및 서식 규칙 엄수.**
1. **계산 금지**: 제공된 원국 데이터를 그대로 쓰십시오.
2. **주인공 고정**: 반드시 **일주(Day)의 첫 글자**를 기준으로 분석하십시오.
3. **즉시 시작**: 응답은 반드시 (줄바꿈 후) `## ` (샵 뒤 공백 필수)로 시작하십시오.

[User Data] {name}({gender_str})
[Natal Chart] {natal_context['year']['stem']}{natal_context['year']['branch']}/{natal_context['month']['stem']}{natal_context['month']['branch']}/{natal_context['day']['stem']}{natal_context['day']['branch']}/{natal_context['hour']['stem']}{natal_context['hour']['branch']}
[Target Date] {target_date.strftime('%Y-%m-%d')} (일진:{target_context['day']['stem']}{target_context['day']['branch']}, 월운:{target_context['month']['stem']}{target_context['month']['branch']})


## 📅 {target_date.strftime('%m월 %d일')} 오늘의 운세 요약
- 한 줄 요약

## 🌟 오늘의 주요 기운 (십신)
- 주요 십신 의미와 오늘 흐르는 에너지 설명

## 💡 선생님을 위한 조언
- 행동 지침 및 주의사항 (짧게)

## 🍀 행운 코드
- 행운의 시간: 
- 행운의 색상: 
"""

def get_prompt(mode, data, chart_context=None):
    """모드에 따른 프롬프트 반환"""
    if mode == 'teacher':
        return get_teacher_prompt(data, chart_context)
    return get_general_prompt(data, chart_context)
