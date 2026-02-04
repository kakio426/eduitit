# 🛠️ Eduitit Service Integration Standard (SIS)

이 문서는 `eduitit` 서비스에 새로운 기능을 추가할 때 사용하는 **공통 표준 가이드**입니다. 이 문석의 규격을 따름으로써 코드의 일관성을 유지하고, 버그를 최소화하며, AI가 즉시 실행 가능한 코드를 생성할 수 있도록 돕습니다.

---

## 1. 서비스 소개 표준 (Blueprint)
새로운 서비스를 정의할 때 아래 요소를 포함하여 기술합니다.

- **아이콘 & 테마**: 이모지(예: 🎨) + 메인 컬러(`purple`, `green`, `red`, `blue`, `orange`)
- **App 위치 (독립성)**: 새로운 대형 서비스는 반드시 별도의 Django App(예: `ssambti`, `autoarticle`)으로 구성합니다. 기존 앱(예: `fortune`, `products`) 내부에 기생하는 구조를 절대 금지하며(예: DutyTicker), 각 앱은 독립적인 `models.py`, `views.py`, `urls.py`를 가져야 합니다.
- **핵심 가치**: 사용자(선생님)가 이 도구로 얻는 구체적인 이득

---

## 2. 인프라 및 기술 스택 표준 (Infrastructure Stack)
본 프로젝트는 다음의 SSOT(Single Source of Truth) 기술 스택을 기반으로 합니다.

- **Framework**: **Django Vanilla (4.2+)** - 복잡한 의존성 없이 장고의 기본 기능을 우선 활용합니다.
- **Deployment**: **Railway** - `Procfile` 기반의 배포를 준수하며, 모든 설정은 환경 변수(`env`)로 관리합니다.
- **Database**: **Neon (Postgres)** - 서버리스 DB 환경이므로, 배포 전 반드시 `makemigrations`를 완료하고 배포 시 자동으로 실행되도록 설정합니다.
- **Admin Path**: 보안을 위해 `secret-admin-kakio/` 경로를 사용합니다.

---

## 3. 기술적 격리 표준 (Technical Isolation Rules)
각 서비스가 '기생'하지 않고 독립적으로 작동하도록 다음 구조를 반드시 준수합니다.

- **URL Namespace**: `config/urls.py`에 등록 시 반드시 `namespace`를 지정합니다.
  - 예: `path('ssambti/', include('ssambti.urls', namespace='ssambti'))`
- **Template Scoping**: 템플릿 파일은 반드시 `app_name/templates/app_name/` 폴더 안에 위치해야 합니다. 
  - (O) `ssambti/templates/ssambti/main.html`
  - [Rule] 절대 타 앱의 템플릿(예: `fortune/zoo_main.html`)을 빌려 쓰지 마십시오.
- **Static Scoping**: 정적 파일 역시 `app_name/static/app_name/` 경로를 준수하여 타 앱과의 파일명 충돌을 방지합니다.

---

## 4. 디자인 시스템 (UI/UX Standard)

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
    <p class="text-xl text-gray-500">설명 문구 (표준 폰트 적용 - Dongle 금지)</p>
</div>
```

### B. 컬러 가이드 (Tailwind)
- **Background**: `bg-[#E0E5EC]`
- **Primary**: `text-purple-600` / `bg-purple-500`
- **Success**: `text-green-600` / `bg-green-500`
- **Warning**: `text-orange-600` / `bg-orange-500`

---

## 4. 코드 아키텍처 (Code Pattern)

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
                <textarea name="content" class="w-full clay-inner p-6 rounded-3xl text-2xl mb-6 focus:outline-none" 
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

### C. Models: 데이터 영속성 (Persistence Standard)
사용자의 활동 기록이나 결과(예: 테스트 결과, 생성된 아티클)를 저장해야 하는 서비스는 반드시 전용 `models.py`를 정의하여 DB 레이어를 구현합니다.

```python
from django.db import models
from django.contrib.auth.models import User

class ServiceResult(models.Model):
    """[Rule] 서비스별 결과 저장 모델 구성 필수"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='service_results')
    # ... 필드 정의 ...
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
```
```

---

## 5. AI 연동 표준 (Gemini Hybrid API)
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

## 6. 와이어프레임 & 네비게이션
1. **대시보드 노출**: `Product` 모델에 `is_active=True`로 등록.
2. **진입 경로**: `dashboard.html`에서 클릭 시 `unifiedModal`을 통해 프리뷰 노출 후 이동.
3. **뒤로가기**: 항상 상단 네비게이션의 로고를 통해 홈으로 이동 가능하도록 `base.html` 준수.

---

---

## 7. 바이브 코딩 및 에이전트 표준 (2026 Vibe Coding Standards)
2026년 에이전트 중심 개발(Software 3.0)의 권위 있는 지침을 본 프로젝트에 이식합니다.

### A. 의도 기반 계획 (Intent-First Planning)
- **Rule**: 코드를 작성하기 전, 에이전트는 반드시 `Implementation Plan`을 제안하고 사용자의 승인을 받아야 합니다.
- **Focus**: 기능의 구현 방식보다 "사용자가 느낄 경험(Vibe)"과 "비즈니스 논리"에 집중하여 설명합니다.

### B. 에이전트 가독성 로그 (AI-Ready Logging)
- **Rule**: 모든 주요 비즈니스 로직에는 에이전트가 사후에 버그를 추적하기 용이하도록 상세 로그를 남깁니다.
- **Standard**: `logger.info(f"[Service_Name] Action: {action}, Status: SUCCESS, Context: {context}")` 형식을 권장합니다.

### C. 터미널 중심 검증 (Terminal-First Verification)
- **Rule**: 브라우저를 열어 확인하기 전, 반드시 터미널 도구를 사용하여 1차 검증을 완료합니다. 브라우저 에이전트 사용은 토큰 낭비가 심하므로 최후의 수단으로만 사용합니다.
- **Tools**: 
  - `python manage.py check`: 시스템 설정 및 모델 무결성 확인
  - `python manage.py shell`: 비즈니스 로직(AI 프롬프트 생성, 데이터 계산 등)의 단위 테스트
- **Vibe Check**: 제작된 HTML/CSS 코드를 정적으로 분석하여 디자인 가이드(Claymorphism) 준수 여부를 확인하며, 실제 렌더링은 사용자가 직접 확인하는 것을 원칙으로 합니다.

---

## 8. 서비스 이관 및 리팩토링 가이드 (Refactoring Guide)
잘못된 위치(예: 타 앱의 내부)에 구현된 서비스를 독립 앱으로 분리할 때의 절차입니다.

1. **상태 백업**: 기존 DB에 데이터가 있다면 `python manage.py dumpdata fortune.ZooResult > backup.json` 등으로 백업합니다.
2. **코드 물리적 이동**: 파일들을 새 앱으로 이동 후, `AppConfig`의 `name`을 확인합니다.
3. **참조 수정**: `views.py` 내의 `from .models` 등 상대 경로 및 절대 경로 임포트를 전수 조사하여 수정합니다.
4. **마이그레이션 정리**: 기존 앱의 `models.py`에서 관련 클래스를 삭제하고 `makemigrations`를 수행하여 DB 관계를 끊습니다.

## 8. 오류 방지 체크리스트 (Bug-Free Checklist)
- [ ] `{% csrf_token %}`이 모든 POST 폼에 포함되었는가?
- [ ] HTMX 사용 시 `HX-Request` 헤더를 체크하여 Partial Template을 반환하는가?
- [ ] 정적 파일(JS/CSS) 사용 시 `{% static %}` 태그를 사용했는가?
- [ ] 사용자 프로필(`UserProfile`)이 없는 경우를 대비해 `hasattr` 체크를 하는가?
- [ ] 모바일 뷰에서 `clay-card`의 패딩이 너무 넓지 않은가? (md:p-14, p-6 분리)
- [ ] **[중요]** 해당 서비스가 독자적인 Django App으로 분리되어 있으며, 전용 `models.py`를 통해 데이터 영속성이 구현되었는가?
- [ ] AI 로깅이 포함되어 있어 추후 에이전트가 자가 수복(Self-healing)하기 용이한가?
- [ ] **[Design]** `Dongle` 폰트가 사용되지 않았으며, 나눔스퀘어라운드/Inter를 사용하는가?
- [ ] **[Design]** "마케팅 용도" 등 불필요한 개인정보 수집 문구가 삭제되었는가?
- [ ] **[UI]** 회원 탈퇴(Delete Account) 기능이 설정 페이지에 포함되었는가?
- [ ] 사용자 경험(UX) 측면에서 `vibe_check`를 완료했는가? (브라우저 없이 코드로 직접 확인)
- [ ] **[Efficiency]** 모든 로직 검증을 브라우저 실행 없이 터미널(`shell`, `check`)에서 완료했는가?
- [ ] **[Infra]** 새로운 모델 추가 시 `makemigrations`를 수행했는가?
- [ ] **[Infra]** Railway 배포를 위해 필요한 환경 변수(`env`) 설정 리스트를 정리했는가?

---
**이 가이드는 `eduitit`의 바이브를 유지하며 가장 빠르게 서비스를 출시하기 위한 약속입니다.**
