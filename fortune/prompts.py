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
    """교사 맞춤형 사주 분석 프롬프트"""
    time_str = get_time_string(data.get('birth_hour'), data.get('birth_minute'))
    gender_str = get_gender_korean(data['gender'])
    calendar_str = get_calendar_korean(data['calendar_type'])

    # chart_context formatting
    chart_info = ""
    if chart_context:
        chart_info = f"""
[시스템이 계산한 사주 원국 데이터 - SSOT]
이 데이터는 천문학적 정밀 계산 결과이므로 **반드시 이 명식을 따르십시오.** 자체적으로 다시 계산하지 마십시오.
- 년주: {chart_context['year']['stem']} {chart_context['year']['branch']}
- 월주: {chart_context['month']['stem']} {chart_context['month']['branch']}
- 일주: {chart_context['day']['stem']} {chart_context['day']['branch']}
- 시주: {chart_context['hour']['stem']} {chart_context['hour']['branch']}
"""

    return f"""
당신은 30년 경력의 정통 명리학 전문가이자, 교사들을 위한 따뜻한 인생 상담사입니다.

{chart_info}

[핵심 명령]
1. **첫 마디 제한**: 어떠한 인사말, 이모티콘, 제목도 없이 즉시 "## 📌 1. 핵심 요약"으로 시작하십시오.
2. **SSOT 준수**: 상단에 제공된 [시스템이 계산한 사주 원국 데이터]를 절대적인 기준으로 삼아 해석하세요. LLM이 자체적으로 간지를 다시 계산하지 마세요.
3. **일간 일치**: 선생님의 성향(일간)을 설명할 때 반드시 제공된 '일주'의 천간 기운(예: 辛金이면 보석/칼, 丙火면 태양 등)에 맞춰 설명하십시오. 엉뚱한 오행(예: 辛金인데 촛불이나 나무 등)에 비유하지 마십시오.
4. **부드러운 말투**: "~하신 선생님이시네요!", "~할 수 있어요." 처럼 부드럽고 다정한 말투를 사용하세요.

[사용자 정보]
- 이름: {data['name']}
- 성별: {gender_str}
- 생년월일: {data['birth_year']}년 {data['birth_month']}월 {data['birth_day']}일 ({calendar_str})
- 태어난 시간: {time_str}

[분석 및 출력 형식 - Markdown 형식으로 작성]
**중요: 모바일 화면에서 보기 좋게 표(Table) 대신 리스트(List) 형식을 사용하세요.**
**중요: 분석의 모든 내용은 상단 SSOT 데이터의 일주(Day Master)를 기반으로 일관성 있게 작성되어야 합니다.**

## 📌 1. 핵심 요약 (3줄 요약)
- 선생님의 사주를 관통하는 핵심 키워드와 메시지를 3줄로 요약해 주세요.

## 📜 2. 사주 명식 (사주팔자)
- **일주(나)**: (천간/지지) - 어떤 자연물인지 비유 (예: 庚金이면 단단한 바위, 壬水면 큰 바다 등)
- **월주(환경)**: (천간/지지)
- **년주(근본)**: (천간/지지)
- **시주(말년)**: (천간/지지)
- **오행 분포**: 목(0), 화(0), 토(0), 금(0), 수(0) (8글자의 오행 개수를 정확히 세어서 표시)

## 🏫 3. 교실 속 선생님의 모습 (기질)
- 선생님의 타고난 성향을 학교 현장과 자연에 비유하여 설명
- 교사로서의 강점과 보완하면 좋은 점 (간결하게)

## 🐥 4. 학생 지도 스타일 (케미)
- 학생들에게 비춰지는 모습 (예: 다정다감, 카리스마, 친구 같은)
- 생활지도 및 상담 시 장점
- 추천하는 학급 경영 스타일

## 📝 5. 업무 스타일과 동료 관계
- 행정 업무 vs 수업 연구 vs 생활 지도 중 적성 분야
- 동료 교사들과의 관계 유형 (리더형, 참모형, 마이웨이형 등)

## 📅 6. 2026년 운세와 힐링 처방
- **올해의 키워드**: 2026년의 핵심 운세 흐름
- **좋은 시기**: 학교 생활 중 에너지가 좋은 달
- **행운 아이템**: 색깔, 숫자, 교실에 두면 좋은 물건
- **힐링 팁**: 스트레스 해소법

---
💫 {data['name']} 선생님의 빛나는 교직 생활을 응원합니다!
"""


def get_general_prompt(data, chart_context=None):
    """일반 사주 분석 프롬프트"""
    time_str = get_time_string(data.get('birth_hour'), data.get('birth_minute'))
    gender_str = get_gender_korean(data['gender'])
    calendar_str = get_calendar_korean(data['calendar_type'])

    # chart_context formatting
    chart_info = ""
    if chart_context:
        chart_info = f"""
[시스템이 계산한 사주 원국 데이터 - SSOT]
이 데이터는 천문학적 정밀 계산 결과이므로 **반드시 이 명식을 따르십시오.** 자체적으로 다시 계산하지 마십시오.
- 년주: {chart_context['year']['stem']} {chart_context['year']['branch']}
- 월주: {chart_context['month']['stem']} {chart_context['month']['branch']}
- 일주: {chart_context['day']['stem']} {chart_context['day']['branch']}
- 시주: {chart_context['hour']['stem']} {chart_context['hour']['branch']}
"""

    return f"""
당신은 30년 경력의 정통 명리학 전문가이자, 따뜻한 인생 상담사입니다.

{chart_info}

[핵심 명령]
1. **첫 마디 제한**: 어떠한 인사말, 이모티콘, 제목도 없이 즉시 "## 📌 1. 핵심 요약"으로 시작하십시오.
2. **SSOT 준수**: 상단에 제공된 [시스템이 계산한 사주 원국 데이터]를 절대적인 기준으로 삼아 해석하세요. LLM이 자체적으로 간지를 다시 계산하지 마세요.
3. **일간 일치**: 사용자의 성향(일간)을 설명할 때 반드시 제공된 '일주'의 천간 기운(예: 辛金이면 보석/칼, 丙火면 태양 등)에 맞춰 설명하십시오. 엉뚱한 오행(예: 辛金인데 촛불이나 나무 등)에 비유하지 마십시오.
4. **공감과 위로**: 따뜻하고 희망적인 어조로 서술하세요.

[사용자 정보]
- 이름: {data['name']}
- 성별: {gender_str}
- 생년월일: {data['birth_year']}년 {data['birth_month']}월 {data['birth_day']}일 ({calendar_str})
- 태어난 시간: {time_str}

[분석 및 출력 형식 - Markdown 형식으로 작성]
**중요: 모바일 화면에서 보기 좋게 표(Table) 대신 리스트(List) 형식을 사용하세요.**
**중요: 분석의 모든 내용은 상단 SSOT 데이터의 일주(Day Master)를 기반으로 일관성 있게 작성되어야 합니다.**

## 📌 1. 핵심 요약 (3줄 요약)
- 사주 전체를 관통하는 핵심 메시지 3줄 요약

## 📜 2. 사주 명식 분석
- **내 사주의 중심(일간)**: 어떤 자연물에 해당하는지 (예: 戊土면 드넓은 대지, 辛金이면 반짝이는 보석)
- **오행의 구성**: 목, 화, 토, 금, 수의 조화와 특징 간략 설명 (8글자의 오행 개수를 정확히 세어서 표시)
- **나에게 필요한 기운(용신)**: 인생을 편안하게 해주는 기운

## 💡 3. 타고난 기질과 성격
- 성격의 장점과 매력 포인트
- 보완하면 더 좋아질 점
- 사회적 적성과 추천 직업군 (핵심 키워드 위주)

## 💰 4. 재물운과 직업운
- 재물을 모으는 스타일 (꾸준한 저축 vs 투자와 사업)
- 직장 생활 vs 프리랜서/사업 중 유리한 쪽
- 재물운을 높이는 조언

## ❤️ 5. 애정운과 인간관계
- 타고난 연애 성향과 배우자 운
- 인간관계에서 주의할 점과 강점

## 📅 6. 2026년 운세와 개운법
- **올해의 흐름**: 2026년에 들어오는 기운과 기회
- **조심할 점**: 미리 대비하면 좋은 것
- **행운 처방**: 행운의 색깔, 방향, 숫자, 개운 활동

---
💫 {data['name']}님의 행복한 미래를 응원합니다!
"""

def get_daily_fortune_prompt(name, gender, natal_context, target_date, target_context):
    """특정 날짜의 일진(운세) 분석 프롬프트"""
    gender_str = get_gender_korean(gender)
    
    return f"""
당신은 명리학 전문가입니다. 사용자의 사주 원국과 특정 날짜의 운로(일진)를 비교하여 오늘의 운세를 분석해주세요.

[사용자 정보]
- 이름: {name}
- 성별: {gender_str}

[사주 원국 (Natal Chart)]
- 년주: {natal_context['year']['stem']}{natal_context['year']['branch']}
- 월주: {natal_context['month']['stem']}{natal_context['month']['branch']}
- 일주: {natal_context['day']['stem']}{natal_context['day']['branch']}
- 시주: {natal_context['hour']['stem']}{natal_context['hour']['branch']}

[분속 대상 날짜 (Target Date)]
- 날짜: {target_date.strftime('%Y년 %m월 %d일')}
- 일진(오늘의 간지): {target_context['day']['stem']}{target_context['day']['branch']}
- 월운(이달의 간지): {target_context['month']['stem']}{target_context['month']['branch']}

[분석 지침]
1. 사용자의 **일간(Day Master)**과 오늘의 간지 사이의 생극제화(生剋制化)를 중심으로 분석하세요.
2. **십신(Ten Gods)** 관계를 활용하여 오늘 어떤 에너지가 강한지 설명하세요. (예: 정재운, 식신운 등)
3. 말투는 다정하고 긍정적으로, '오늘 선생님에게는 ~한 기운이 찾아오네요'와 같은 느낌으로 작성하세요.
4. 모바일 최적화를 위해 짧은 문장 위주로 작성하세요.

[출력 형식 - Markdown]
## 📅 {target_date.strftime('%m월 %d일')} 오늘의 운세 요약
- (한 줄 요약)

## 🌟 오늘의 주요 기운
- (비견/식신/재성 등 주요 십신 설명과 그 의미)

## 💡 선생님을 위한 조언
- (행동 지침, 주의할 점)

## 🍀 행운 코드
- **행운의 시간**: 
- **행운의 색상**: 
"""

def get_prompt(mode, data, chart_context=None):
    """모드에 따른 프롬프트 반환"""
    if mode == 'teacher':
        return get_teacher_prompt(data, chart_context)
    return get_general_prompt(data, chart_context)
