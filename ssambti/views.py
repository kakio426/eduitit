from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from products.models import Product
from .models import SsambtiResult
from .mbti_data import MBTI_RESULTS

from django.conf import settings

MBTI_ANIMAL_MAP = {
    'ISTJ': 'penguin.png',
    'ISFJ': 'quokka.png',
    'INFJ': 'snow_leopard.png',
    'INTJ': 'black_cat.png',
    'ISTP': 'raccoon.png',
    'ISFP': 'koala.png',
    'INFP': 'sea_otter.png',
    'INTP': 'owl.png',
    'ESTP': 'cheetah.png',
    'ESFP': 'dolphin.png',
    'ENFP': 'red_panda.png',
    'ENTP': 'meerkat.png',
    'ESTJ': 'tiger.png',
    'ESFJ': 'elephant.png',
    'ENFJ': 'golden_retriever.png',
    'ENTJ': 'lion.png',
}

def main_view(request):
    """
    [SIS Standard] 쌤BTI 메인 뷰 (12문항 버전)
    """
    service = Product.objects.filter(title__icontains="쌤BTI").first()
    if not service:
        service = Product.objects.filter(title__icontains="티처블 동물원").first()
    
    is_premium = False
    if service and request.user.is_authenticated:
        is_premium = request.user.owned_products.filter(product=service).exists()

    context = {
        'service': service,
        'title': service.title if service else "쌤BTI",
        'icon': "🦁", 
        'description': "12가지 질문으로 알아보는 디테일한 교실 속 자아 찾기!",
        'is_premium': is_premium,
        'KAKAO_JS_KEY': settings.KAKAO_JS_KEY
    }
    return render(request, 'ssambti/main.html', context)

@require_POST
def analyze_view(request):
    """
    [SIS Standard] 12가지 답변을 종합하여 MBTI 분석 수행 및 저장 (정적 데이터 방식)
    """
    import time
    time.sleep(3)  # 신비로운 분위기를 위한 인위적 지연 (총 로드 시간 약 4초 예상)
    
    # 12개 질문에 대한 답변 수집
    answers = {}
    for i in range(1, 13):
        val = request.POST.get(f'q{i}', '무응답')
        answers[f'q{i}'] = val
    
    # MBTI 판정 로직 (인덱스 기반: 0=앞파벳, 1=뒷알파벳)
    # Q1-3: E/I, Q4-6: S/N, Q7-9: T/F, Q10-12: J/P
    
    # 각 지표별로 인덱스 0(앞)을 선택한 횟수를 카운트
    def get_dim_count(start, end):
        count_0 = 0
        for i in range(start, end + 1):
            val = answers.get(f'q{i}', '0')
            if str(val) == '0':
                count_0 += 1
        return count_0

    # 3개씩 끊어서 앞 알파벳이 2개 이상이면 해당 알파벳 선택
    mbti_type = ''
    mbti_type += 'E' if get_dim_count(1, 3) >= 2 else 'I'
    mbti_type += 'S' if get_dim_count(4, 6) >= 2 else 'N'
    mbti_type += 'T' if get_dim_count(7, 9) >= 2 else 'F'
    mbti_type += 'J' if get_dim_count(10, 12) >= 2 else 'P'
    
    # 정적 데이터에서 결과 가져오기
    result_data = MBTI_RESULTS.get(mbti_type, MBTI_RESULTS['ENFP'])  # 기본값: ENFP
    animal_name = result_data['animal_name']
    
    # HTML 생성
    result_html = f"""
    <div class="space-y-8 text-left animate-fade-in-up">
        
        <!-- 1. 영혼의 메시지 (가장 중요) -->
        <div class="clay-card p-8 bg-white/80 border-l-8 border-orange-400">
            <h3 class="text-3xl font-bold text-gray-800 mb-6 font-title flex items-center gap-2">
                <span class="text-4xl">💌</span> 선생님을 위한 영혼의 메시지
            </h3>
            <p class="text-3xl text-gray-600 leading-relaxed font-hand whitespace-pre-line">
                "{result_data['soul_message']}"
            </p>
        </div>

        <!-- 2. 교실 속 자아 분석 -->
        <div class="clay-card p-8 bg-[#fdfbf7]">
            <h3 class="text-3xl font-bold text-gray-800 mb-6 font-title flex items-center gap-2">
                <span class="text-4xl">🏫</span> 교실 속 {animal_name} 선생님은?
            </h3>
            <div class="space-y-6">
                <div>
                    <span class="badge badge-orange mb-3 text-lg">평소 모습</span>
                    <p class="text-2xl text-gray-700 font-hand leading-relaxed">{result_data['normal']}</p>
                </div>
                <div>
                    <span class="badge badge-purple mb-3 text-lg">스트레스 받을 때</span>
                    <p class="text-2xl text-gray-700 font-hand leading-relaxed">{result_data['stress']}</p>
                </div>
                <div>
                    <span class="badge badge-green mb-3 text-lg">최고의 순간</span>
                    <p class="text-2xl text-gray-700 font-hand leading-relaxed">{result_data['best_moment']}</p>
                </div>
            </div>
        </div>

        <!-- 3. 최고의 짝꿍 / 최악의 짝꿍 -->
        <div class="grid md:grid-cols-2 gap-6">
            <div class="clay-card p-6 bg-green-50/50">
                <div class="flex items-center gap-3 mb-4">
                    <div class="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center text-2xl">🥰</div>
                    <h3 class="text-2xl font-bold text-green-800 font-title">찰떡궁합 학생</h3>
                </div>
                <p class="text-gray-600 font-hand text-2xl leading-relaxed">{result_data['good_student']}</p>
            </div>
            <div class="clay-card p-6 bg-red-50/50">
                <div class="flex items-center gap-3 mb-4">
                    <div class="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center text-2xl">🤯</div>
                    <h3 class="text-2xl font-bold text-red-800 font-title">조심해야 할 상황</h3>
                </div>
                <p class="text-gray-600 font-hand text-2xl leading-relaxed">{result_data['caution']}</p>
            </div>
        </div>

        <!-- 4. 처방전 -->
        <div class="clay-card p-8 bg-purple-50/50 text-center">
            <h3 class="text-3xl font-bold text-purple-800 mb-6 font-title">
                🎁 {animal_name} 선생님을 위한 힐링 처방전
            </h3>
            <p class="text-3xl text-gray-600 font-hand leading-relaxed">
                "{result_data['prescription']}"
            </p>
        </div>
    </div>
    """
    
    # 결과 저장 (로그인 사용자만)
    if request.user.is_authenticated:
        SsambtiResult.objects.create(
            user=request.user,
            mbti_type=mbti_type,
            animal_name=animal_name,
            result_text=result_html,
            answers_json=answers
        )
    
    # 공유용 요약 문구 생성
    taglines = {
        'ISTJ': '철저한 준비와 원칙으로 신뢰를 주는 기둥',
        'ISFJ': '따뜻한 미소와 세심함으로 교실을 보듬는 쿼카',
        'INFJ': '아이들의 잠재력을 꿰뚫어 보는 통찰력 가득 멘토',
        'INTJ': '본질을 뚫어보는 날카롭고 전략적인 설계자',
        'ISTP': '어떤 위기에도 침착하게 해답을 찾아내는 해결사',
        'ISFP': '아이들의 개성을 존중하는 온화한 예술가',
        'INFP': '진심 어린 공감으로 아이들의 마음을 여는 영혼',
        'INTP': '지적 호기심으로 아이들의 생각을 깨우는 학자',
        'ESTP': '에너지 넘치는 순발력으로 교실을 사로잡는 치타',
        'ESFP': '긍정 에너지로 교실을 축제로 만드는 돌고래',
        'ENFP': '무한한 상상력으로 아이들에게 영감을 주는 마법사',
        'ENTP': '비판적 사고와 재치로 배움의 즐거움을 깨우는 미어캣',
        'ESTJ': '확고한 리더십으로 올바른 길을 안내하는 나침반',
        'ESFJ': '세심한 배려로 모두를 하나로 묶는 교실의 엄마/아빠',
        'ENFJ': '헌신적인 열정으로 아이들의 인생을 바꾸는 멘토',
        'ENTJ': '강력한 비전으로 더 높은 곳을 바라보게 하는 리더'
    }
    summary = taglines.get(mbti_type, '교실 속 특별한 영혼을 가진 선생님')

    animal_image = MBTI_ANIMAL_MAP.get(mbti_type, 'lion.png')

    return render(request, 'ssambti/partials/result.html', {
        'result_html': result_html, 
        'KAKAO_JS_KEY': settings.KAKAO_JS_KEY,
        'animal_image': animal_image,
        'mbti_type': mbti_type,
        'animal_name': animal_name,
        'summary': summary
    })

@login_required
def history_view(request):
    """결과 보관함 목록"""
    history = SsambtiResult.objects.filter(user=request.user)
    # Add image mapping to history items
    for item in history:
        item.animal_image = MBTI_ANIMAL_MAP.get(item.mbti_type, 'lion.png')
    return render(request, 'ssambti/history.html', {'history': history})

@login_required
def detail_view(request, pk):
    """특정 결과 상세보기 (공유 페이지로도 활용 가능)"""
    result = get_object_or_404(SsambtiResult, pk=pk) 
    animal_image = MBTI_ANIMAL_MAP.get(result.mbti_type, 'lion.png')
    return render(request, 'ssambti/detail.html', {
        'result': result, 
        'animal_image': animal_image,
        'KAKAO_JS_KEY': settings.KAKAO_JS_KEY
    })
