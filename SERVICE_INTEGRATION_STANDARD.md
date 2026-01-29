# 🛠️ Eduitit Service Integration Standard (SIS)

이 문서는 `eduitit` 서비스에 새로운 기능을 추가할 때 사용하는 **공통 표준 가이드**입니다. 이 문석의 규격을 따름으로써 코드의 일관성을 유지하고, 버그를 최소화하며, AI가 즉시 실행 가능한 코드를 생성할 수 있도록 돕습니다.

---

## 1. 서비스 소개 표준 (Blueprint)
새로운 서비스를 정의할 때 아래 요소를 포함하여 기술합니다.

- **아이콘 & 테마**: 이모지(예: 🎨) + 메인 컬러(`purple`, `green`, `red`, `blue`, `orange`)
- **App 위치**: `products` (일반 도구), `fortune` (AI/운세), `core` (시스템 공통)
- **핵심 가치**: 사용자(선생님)가 이 도구로 얻는 구체적인 이득

---

## 2. 디자인 시스템 (UI/UX Standard)

### A. Claymorphism 규격
모든 카드는 `clay-card` 클래스를 사용하며, 배경색은 `#E0E5EC`를 기본으로 합니다.

```html
<!-- 표준 카드 레이아웃 -->
<div class="clay-card p-8 group hover:shadow-clay-hover transition-all duration-300">
    <!-- 아이콘 영역 -->
    <div class="w-20 h-20 rounded-full shadow-clay-inner flex items-center justify-center text-4xl mb-6 float-icon">
        🎨
    </div>
    <!-- 텍스트 영역 -->
    <h3 class="text-3xl font-bold text-gray-700 mb-2 font-title">서비스 제목</h3>
    <p class="text-xl text-gray-500 font-hand">설명 문구 (Dongle 폰트 적용)</p>
</div>
```

### B. 컬러 가이드 (Tailwind)
- **Background**: `bg-[#E0E5EC]`
- **Primary**: `text-purple-600` / `bg-purple-500`
- **Success**: `text-green-600` / `bg-green-500`
- **Warning**: `text-orange-600` / `bg-orange-500`

---

## 3. 코드 아키텍처 (Code Pattern)

### A. View: 비즈니스 로직 (Python)
유지보수가 쉽도록 전용 함수와 공통 믹스인을 활용합니다.

```python
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from products.models import Product

@login_required
def service_main_view(request):
    """
    [Rule]
    1. Product 모델에서 서비스 정보를 가져와 context에 포함 (아이콘/컬러 동기화)
    2. 에러 처리는 try-except로 감싸고 사용자에게 친절한 메시지 반환
    """
    service = Product.objects.filter(title__icontains="서비스명").first()
    
    context = {
        'service': service,
        'title': service.title if service else "서비스명",
        'is_premium': request.user.owned_products.filter(product=service).exists()
    }
    return render(request, 'app_name/service_template.html', context)
```

### B. Template: 레이아웃 (HTML + HTMX)
단일 페이지 경험(SPA)을 위해 **HTMX**를 적극 활용합니다.

```html
{% extends 'base.html' %}

{% block content %}
<section class="pt-32 pb-20 px-6 min-h-screen">
    <div class="max-w-5xl mx-auto">
        <!-- 상단 헤더 섹션 -->
        <div class="text-center mb-12" data-aos="fade-up">
            <div class="text-7xl mb-4 float-icon">{{ service.icon }}</div>
            <h1 class="text-5xl font-bold text-gray-700 font-title">{{ title }}</h1>
        </div>

        <!-- 메인 액션 영역 -->
        <div class="clay-card p-10" data-aos="zoom-in">
            <form hx-post="{% url 'api_endpoint' %}" 
                  hx-target="#result-area" 
                  hx-indicator="#loading-spinner">
                {% csrf_token %}
                <textarea name="content" class="w-full clay-inner p-6 rounded-3xl text-2xl font-hand mb-6 focus:outline-none" 
                          placeholder="여기에 내용을 입력하세요..."></textarea>
                
                <button type="submit" class="w-full py-5 bg-purple-500 text-white rounded-full text-2xl font-bold shadow-clay hover:shadow-clay-hover transition-all transform active:scale-95">
                    실행하기
                </button>
            </form>
        </div>

        <!-- 결과 표시 영역 -->
        <div id="result-area" class="mt-12">
            <!-- HTMX로 로드될 부분 -->
        </div>

        <!-- 로딩 스피너 -->
        <div id="loading-spinner" class="htmx-indicator fixed inset-0 z-[100] flex items-center justify-center bg-white/50 backdrop-blur-sm">
            <i class="fa-solid fa-circle-notch fa-spin text-6xl text-purple-500"></i>
        </div>
    </div>
</section>
{% endblock %}
```

---

## 4. AI 연동 표준 (Gemini Hybrid API)
`fortune` 앱의 검증된 로직을 재사용합니다.

```python
from fortune.views import generate_ai_response

def process_with_ai(request):
    user_input = request.POST.get('content')
    prompt = f"선생님 관점에서 다음 내용을 분석해줘: {user_input}"
    
    # [SIS Rule] 반드시 request를 인자로 넘겨 사용자 개인 키 사용 여부를 체크함
    response_text = generate_ai_response(prompt, request)
    
    return render(request, 'app_name/partials/result.html', {'result': response_text})
```

---

## 5. 와이어프레임 & 네비게이션
1. **대시보드 노출**: `Product` 모델에 `is_active=True`로 등록.
2. **진입 경로**: `dashboard.html`에서 클릭 시 `unifiedModal`을 통해 프리뷰 노출 후 이동.
3. **뒤로가기**: 항상 상단 네비게이션의 로고를 통해 홈으로 이동 가능하도록 `base.html` 준수.

---

## 6. 오류 방지 체크리스트 (Bug-Free Checklist)
- [ ] `{% csrf_token %}`이 모든 POST 폼에 포함되었는가?
- [ ] HTMX 사용 시 `HX-Request` 헤더를 체크하여 Partial Template을 반환하는가?
- [ ] 정적 파일(JS/CSS) 사용 시 `{% static %}` 태그를 사용했는가?
- [ ] 사용자 프로필(`UserProfile`)이 없는 경우를 대비해 `hasattr` 체크를 하는가?
- [ ] 모바일 뷰에서 `clay-card`의 패딩이 너무 넓지 않은가? (md:p-14, p-6 분리)

---
**이 가이드는 `eduitit`의 바이브를 유지하며 가장 빠르게 서비스를 출시하기 위한 약속입니다.**
