from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .libs import calculator
from .models import FortuneResult, Stem, Branch
import json
import logging
from datetime import datetime
import pytz
import hashlib

# Re-use existing AI response logic if possible
from .views import generate_ai_response, get_chart_context

logger = logging.getLogger(__name__)

def get_natal_hash(pillars):
    """사주 명식의 8글자를 기반으로 고유 해시 생성"""
    # pillars: {year: {stem: char, branch: char}, ...}
    # We sort to ensure consistency
    text = ""
    for col in ['year', 'month', 'day', 'hour']:
        s = pillars[col]['stem']['char']
        b = pillars[col]['branch']['char']
        text += f"{s}{b}"
    return hashlib.sha256(text.encode()).hexdigest()

def calculate_pillars_only(request):
    """
    Step 1: AI 없이 사주 명식만 즉시 계산
    - 모든 오행 분석을 Python에서 수행 (Mockup 없음)
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
        
        # Calculate Pillars using existing logic
        # get_chart_context handles the datetime and calculator call
        chart_context = get_chart_context(data)
        if not chart_context:
             return JsonResponse({'error': 'Calculation failed'}, status=500)

        # Robust Serialization
        def serialize_column(col_data):
            s = col_data['stem']
            b = col_data['branch']
            return {
                'ganji': f"{s.character if s else ''}{b.character if b else ''}",
                'stem': {'char': s.character if s else '', 'element': s.element if s else ''},
                'branch': {'char': b.character if b else '', 'element': b.element if b else ''}
            }

        pillars = {
            'year': serialize_column(chart_context['year']),
            'month': serialize_column(chart_context['month']),
            'day': serialize_column(chart_context['day']),
            'hour': serialize_column(chart_context['hour']),
        }

        # Element Counting (Real Logic)
        element_counts = {'wood': 0, 'fire': 0, 'earth': 0, 'metal': 0, 'water': 0}
        def add_el(el):
            if el in element_counts: element_counts[el] += 1
            
        for col in pillars.values():
            add_el(col['stem']['element'])
            add_el(col['branch']['element'])
            
        # Day Master
        dm = chart_context['day']['stem']
        
        return JsonResponse({
            'success': True,
            'pillars': pillars,
            'natal_hash': get_natal_hash(pillars),
            'day_master': {
                'char': dm.character if dm else '',
                'element': dm.element if dm else ''
            },
            'element_counts': element_counts
        })

    except Exception as e:
        logger.exception("Calculation Error")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def analyze_topic(request):
    """
    Step 2: 주제별 AI 분석 (DB 캐싱 적용)
    - 로그인 유저는 한 번 본 내용을 자동으로 DB에 저장/로드
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
        pillars = data.get('pillars')
        topic = data.get('topic')
        name = data.get('name', '가입자')
        gender = data.get('gender', 'female')
        natal_hash = data.get('natal_hash') or get_natal_hash(pillars)
        
        # 1. DB Cache Check (For Authenticated Users)
        if request.user.is_authenticated:
            cached_result = FortuneResult.objects.filter(
                user=request.user,
                natal_hash=natal_hash,
                topic=topic
            ).first()
            
            if cached_result:
                logger.info(f"Cache Hit: {request.user.username} - {topic}")
                return JsonResponse({
                    'success': True,
                    'topic': topic,
                    'result': cached_result.result_text,
                    'cached': True
                })

        # 2. Build Prompt
        prompt = build_focused_prompt(topic, pillars, name, gender)

        # 3. Call AI
        response_text = "".join(generate_ai_response(prompt, request))

        # 4. Auto Save (Cache)
        if request.user.is_authenticated and response_text.strip():
            FortuneResult.objects.create(
                user=request.user,
                topic=topic,
                natal_hash=natal_hash,
                natal_chart=pillars,
                result_text=response_text,
                mode='general'
            )

        return JsonResponse({
            'success': True,
            'topic': topic,
            'result': response_text,
            'cached': False
        })

    except Exception as e:
        logger.exception(f"Analysis Error ({topic})")
        return JsonResponse({'error': str(e)}, status=500)

def build_focused_prompt(topic, pillars, name, gender):
    """주제별 특화 프롬프트 생성을 위한 헬퍼 (Mockup 제거)"""
    chart_str = f"년:{pillars['year']['ganji']}, 월:{pillars['month']['ganji']}, 일:{pillars['day']['ganji']}, 시:{pillars['hour']['ganji']}"
    dm_char = pillars['day']['stem']['char']
    
    role = "30년 경력의 명리 전문가 (다정하고 심오한 어조)"
    constraints = "서론/본론 생략하고 바로 마크다운 ## 소제목으로 시작할 것. 자연물에 비유하여 깊이 있게 설명."

    prompts = {
        'personality': f"""
            [Role] {role}
            [Target] {name}({gender}), 일간: {dm_char}
            [Chart] {chart_str}
            ## 🐯 타고난 기질과 성격 분석
            - {dm_char} 일간의 본질과 자연적 비유
            - 사회적 모습과 내면적 갈등/조화
            - 당신만이 가진 고유한 매력 포인트
        """,
        'wealth': f"""
            [Role] {role} (재물운 전문)
            [Target] {name}({gender})
            [Chart] {chart_str}
            ## 💰 재물운과 경제적 흐름
            - 재물 그릇의 형태와 성격 (식상생재, 재생관 등 명리적 근거 포함)
            - 돈이 들어오는 통로와 나가는 구멍 관리법
            - 큰 부자가 되기 위한 개운법
        """,
        'career': f"""
            [Role] {role} (진로/직업 전문)
            [Target] {name}({gender})
            [Chart] {chart_str}
            ## 💼 직업 적성과 성공 전략
            - 가장 실력을 발휘할 수 있는 분야와 포지션
            - 조직 내에서의 대인관계 및 승진운
            - 적합한 커리어 로드맵 제안
        """,
        'compatibility': f"""
            [Role] {role} (연애/궁합 전문)
            [Target] {name}({gender})
            [Chart] {chart_str}
            ## ❤️ 연애 성향과 인연 분석
            - 당신의 연애 스타일과 배우자 복 (관성/재성 기준)
            - 귀인이 되어줄 이성의 기운 (오행/십신)
            - 행복한 관계를 위한 마음가짐
        """
    }
    
    return f"{prompts.get(topic, '일반 분석')} \n\n {constraints}"
