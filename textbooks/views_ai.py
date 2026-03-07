import os
import json
import logging
import requests
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import AiUsage

logger = logging.getLogger(__name__)

def call_deepseek_api(prompt, system_prompt=""):
    """DeepSeek API를 호출합니다."""
    # 사용자가 환경변수에 설정한 DEEPSEEK_API_KEY를 사용
    api_key = os.environ.get('DEEPSEEK_API_KEY')
    if not api_key:
        raise Exception("서버에 DEEPSEEK_API_KEY가 설정되지 않았습니다.")
        
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    data = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1500
    }
    
    response = requests.post(url, headers=headers, json=data, timeout=30)
    response.raise_for_status()
    result = response.json()
    return result["choices"][0]["message"]["content"]


@login_required
@require_POST
def auto_categorize(request):
    """제공된 텍스트/코드를 분석하여 가장 적합한 과목과 추천 단원명을 반환합니다."""
    content = request.POST.get('content', '').strip()
    
    if not content:
        return JsonResponse({'success': False, 'error': '내용이 비어있습니다.'}, status=400)
    
    # 사용량 체크
    usage = AiUsage.get_todays_usage(request.user)
    if usage.categorize_count >= 20: # 분류는 좀 더 여유롭게 20번
        return JsonResponse({'success': False, 'error': '일일 AI 자동 분류 횟수(20회)를 초과했습니다.'}, status=403)
        
    prompt = f"""
다음 교육 자료(텍스트 또는 코드)를 분석하여, 우리나라 초·중학교 교육과정 기준 가장 적합한 '과목'과 '단원명(주제)'을 추천해주세요.

[자료 내용]
{content[:2000]}

반드시 아래 JSON 형식으로만 응답하세요. 다른 설명은 제외하세요.
과목 코드는 다음 중 하나여야 합니다: KOREAN(국어), MATH(수학), SOCIAL(사회), SCIENCE(과학). 적합한 것이 없다면 가장 유사한 것을 고르세요.

{{
    "subject_code": "선택된_과목_코드",
    "recommended_unit": "추천하는_단원명_또는_상세_주제(예: 화산과 지진)"
}}
"""
    try:
        response_text = call_deepseek_api(prompt, system_prompt="너는 한국의 교육과정 분석 전문가 AI입니다. 반드시 요구된 JSON 형태만을 응답하세요.")
        cleaned_text = response_text.replace("```json", "").replace("```", "").strip()
        result = json.loads(cleaned_text)
        
        # 횟수 차감(증가)
        usage.categorize_count += 1
        usage.save()
        
        return JsonResponse({
            'success': True,
            'subject_code': result.get('subject_code', ''),
            'recommended_unit': result.get('recommended_unit', '')
        })
        
    except Exception as e:
        logger.error(f"[Textbooks] DeepSeek categorize failed: {e}")
        return JsonResponse({'success': False, 'error': 'AI 분석 중 오류가 발생했습니다. 직접 입력해주세요.'}, status=500)


@login_required
@require_POST
def generate_prompt(request):
    """교사가 입력한 정보로 딥시크 AI 기반 프롬프트를 생성해줍니다. (1일 5회 제한)"""
    usage = AiUsage.get_todays_usage(request.user)
    
    if usage.prompt_count >= 5:
        return JsonResponse({
            'success': False, 
            'error': '일일 프롬프트 도우미 사용 한도(5회)를 모두 소진하셨습니다. 내일 다시 이용해주세요.'
        }, status=403)
        
    subject = request.POST.get('subject', '선택 안 됨')
    grade = request.POST.get('grade', '')
    unit_title = request.POST.get('unit_title', '').strip()
    
    if not unit_title:
        return JsonResponse({'success': False, 'error': '단원명 또는 주제를 입력해주세요.'}, status=400)
        
    prompt = f"""
나는 초등학교(또는 중학교) 교사입니다. 이번 수업을 위해 AI(Claude나 GPT)에 프로그래밍 코딩을 요청하는 '프롬프트'를 짜고 싶습니다.
나를 대신해서 완벽한 요청 프롬프트를 하나 작성해주세요.

[수업 정보]
- 과목: {subject}
- 대상: {grade}
- 주제(단원): {unit_title}

[요구사항]
이 수업의 핵심 개념을 학생들이 스마트폰으로 직접 터치하며 재밌게 학습할 수 있는 "단일 HTML 기반의 상호작용형(Interactive) 시각화 앱"을 만들어 달라고 AI에게 부탁할 예정입니다.
아이들의 흥미를 유발할 수 있는 예시나 게임 요소가 들어가게끔 프롬프트를 유도해주세요.

[주의사항]
반드시 내가 그대로 복사해서 다른 AI 챗봇에 붙여넣을 수 있게, 
"안녕? 나는 초등교사야... 이걸 만들어줘... 1. 한개의 완성된 HTML코드만 줘... 등" 의 1인칭 요청자 시점의 문장으로만 결과물을 작성해주세요.
부연 설명은 절대 하지 마세요.
"""

    try:
        generated_prompt_text = call_deepseek_api(prompt, system_prompt="너는 최고의 프롬프트 엔지니어입니다. 조건에 정확히 맞는 템플릿만 출력합니다.")
        
        # 횟수 증가
        usage.prompt_count += 1
        usage.save()
        
        return JsonResponse({
            'success': True,
            'prompt_text': generated_prompt_text.strip(),
            'remaining_count': 5 - usage.prompt_count
        })
        
    except Exception as e:
        logger.error(f"[Textbooks] DeepSeek prompt config failed: {e}")
        return JsonResponse({'success': False, 'error': 'AI 서버 통신에 실패했습니다.'}, status=500)


@login_required
@require_POST
def generate_quiz(request, pk):
    """
    지정된 자료 내용을 바탕으로 초/중학생 수준의 O/X 혹은 객관식 미니 퀴즈 3문제를 생성합니다. (분류 카운트 공유)
    """
    from .models import TextbookMaterial
    material = TextbookMaterial.objects.filter(pk=pk).first()
    if not material or not material.content:
        return JsonResponse({'success': False, 'error': '자료가 유효하지 않습니다.'}, status=400)

    usage = AiUsage.get_todays_usage(request.user)
    if usage.categorize_count >= 20:
        return JsonResponse({'success': False, 'error': '일일 AI 사용 한도를 모두 소진하셨습니다.'}, status=403)

    prompt = f"""
다음은 내가 만든 수업 자료의 내용입니다:
---
{material.content[:2000]}
---
이 내용을 바탕으로 초/중학생들이 재미있게 풀 수 있는 O/X 퀴즈 3문제를 만들어주세요.
각 문제 아래에 정답과 간단한 해설을 적어주세요.
마크다운 포맷(### 등)이나 특수문자를 최소화하고, 읽기 편한 평문 위주로 작성해주세요.
"""

    try:
        quiz_text = call_deepseek_api(prompt, system_prompt="당신은 아이들 눈높이에 맞춘 친절한 퀴즈 출제 교사입니다.")
        usage.categorize_count += 1
        usage.save()
        
        return JsonResponse({
            'success': True,
            'quiz_text': quiz_text.strip()
        })
        
    except Exception as e:
        logger.error(f"[Textbooks] DeepSeek quiz generation failed: {e}")
        return JsonResponse({'success': False, 'error': 'AI 퀴즈 생성에 실패했습니다.'}, status=500)
