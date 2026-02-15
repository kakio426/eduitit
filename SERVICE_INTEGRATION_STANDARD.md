# 🛠️ Eduitit Service Integration Standard (SIS)

이 문서는 `eduitit` 서비스에 새로운 기능을 추가할 때 사용하는 **공통 표준 가이드**입니다. 이 문석의 규격을 따름으로써 코드의 일관성을 유지하고, 버그를 최소화하며, AI가 즉시 실행 가능한 코드를 생성할 수 있도록 돕습니다.

---

## 1. 서비스 소개 표준 (Blueprint)
새로운 서비스를 정의할 때 아래 요소를 포함하여 기술합니다.

- **아이콘 & 테마**: 이모지(예: 🎨) + 메인 컬러(`purple`, `green`, `red`, `blue`, `orange`)
- **App 위치 (독립성)**: 새로운 대형 서비스는 반드시 별도의 Django App으로 구성합니다. 독립적인 `models.py`, `views.py`, `urls.py`는 필수입니다.
- **모달 풍성함 (Rich Content)**: 서비스를 `Product` 모델에 등록할 때, 다음 요소를 반드시 포함하여 프리뷰 모달이 "빈약해" 보이지 않게 합니다.
  - **Lead Text**: 서비스의 핵심 가치를 담은 매력적인 한 줄 문구.
  - **Description**: 서비스 사용법과 기대 효과를 포함한 2~3문장 이상의 설명.
  - **ProductFeatures**: 최소 3개 이상의 핵심 기능(아이콘+제목+설명)을 등록해야 합니다.
- **용어 표현 (Kid-Friendly)**: 학생용 서비스인 경우 MBTI, 진단 등 딱딱한 용어 대신 '캐릭터', '친구 찾기' 등 학생 친화적인 용어를 사용합니다.
- **Title 일관성 (SSOT)**: 템플릿이나 뷰에서 `product.title`을 조건문이나 검색어로 사용할 경우, 반드시 `products/management/commands/ensure_<app_name>.py`에 정의된 공식 타이틀과 100% 일치해야 합니다. (잘못된 예: DB에는 '우리반 캐릭터'인데 코드에는 '학교생활 캐릭터'로 적는 경우)

---

## 2. 인프라 및 기술 스택 표준 (Infrastructure Stack)
본 프로젝트는 다음의 SSOT(Single Source of Truth) 기술 스택을 기반으로 합니다.

- **Framework**: **Django Vanilla (4.2+)** - 복잡한 의존성 없이 장고의 기본 기능을 우선 활용합니다.
- **Deployment**: **Railway** - `Procfile` 기반의 배포를 준수하며, 모든 설정은 환경 변수(`env`)로 관리합니다.
- **Database**: **Neon (Postgres)** - 서버리스 DB 환경이므로, 배포 전 반드시 `makemigrations`를 완료하고 배포 시 자동으로 실행되도록 설정합니다.
- **Dependency Management**: 새로운 라이브러리(예: `qrcode`, `openpyxl`)를 로컬에서 설치한 경우, 반드시 즉시 `requirements.txt`에 추가해야 합니다. 배포 환경(Railway)은 이 파일을 기준으로 빌드되므로, 누락 시 배포 실패의 원인이 됩니다.
- **Admin Path**: 보안을 위해 `secret-admin-kakio/` 경로를 사용합니다.

---

## 3. 기술적 격리 표준 (Technical Isolation Rules)
각 서비스가 '기생'하지 않고 독립적으로 작동하도록 다음 구조를 반드시 준수합니다.

- **URL Namespace**: `config/urls.py`에 등록 시 반드시 `namespace`를 지정합니다.
  - 예: `path('ssambti/', include('ssambti.urls', namespace='ssambti'))`
- **Template Scoping**: 템플릿 파일은 반드시 `app_name/templates/app_name/` 폴더 안에 위치해야 합니다. 
  - (O) `ssambti/templates/ssambti/main.html`
  - [Rule] 절대 타 앱의 템플릿(예: `fortune/zoo_main.html`)을 빌려 쓰지 마십시오.
- **Static Scoping**: 정적 파일은 반드시 `app_name/static/app_name/` 경로를 준수하여 타 앱과의 파일명 충돌을 방지합니다. (예: `studentmbti/static/studentmbti/images/`)
- **Data Isolation**: 대량의 정적 매핑 데이터(예: 캐릭터 결과 문구)는 `views.py`에 두지 않고 별도의 `student_mbti_data.py` (또는 `constants.py`)로 분리하여 임포트합니다.

---

## 3.1. 교실용 서비스 운영 표준 (Teacher-Student Interaction)

학급 전체가 참여하는 서비스(예: 검사, 퀴즈)는 다음의 **와이어프레임 구조**를 표준으로 합니다.

1. **교사 (Manager Profile)**: 로그인 상태에서 세션(Session/UUID)을 생성하고 실시간 대시보드를 확인합니다.
2. **학생 (Guest Flow)**: 별도의 회원가입/로그인 없이, 교사가 생성한 QR 코드나 URL(UUID 포함)을 통해 즉시 활동에 참여합니다. 
3. **참여 방식**: 학생은 이름(닉네임)과 번호 정도의 최소 정보만 입력 후 결과까지 비로그인 상태로 유지됩니다.
4. **결과 영속성**: 학생의 결과는 `models.py`에 저장되나, 학생 개인은 세션 브라우저 종료 시 권한이 만료되므로 교사가 대시보드에서 관리해 주어야 합니다.

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

### 6.1. Product 자동 등록 표준 (ensure_* Management Command)
새로운 서비스를 추가할 때, 대시보드에 노출되려면 `Product` 테이블에 데이터가 존재해야 합니다. **코드만 배포하고 Product 등록을 누락하면 서비스가 대시보드에 나타나지 않습니다.**

- **Rule**: 모든 신규 서비스는 반드시 `ensure_<app_name>` management command를 생성해야 합니다.
- **위치**: `products/management/commands/ensure_<app_name>.py` (통일 위치. 앱 내부 `management/`에 두지 말 것)
- **4곳 동시 등록 (누락 시 502 에러 발생)**:
  1. `config/settings_production.py` → `INSTALLED_APPS`에 앱 추가
  2. `Procfile` → `migrate` 이후에 `ensure_<app_name>` 커맨드 추가
  3. `nixpacks.toml` → `[phases.start]` 명령에 동일하게 추가 (Procfile과 동기화)
  4. `config/settings_production.py` → `run_startup_tasks()`에 `call_command('ensure_<app_name>')` 추가

```python
# 표준 ensure 커맨드 구조
from django.core.management.base import BaseCommand
from products.models import Product, ProductFeature

class Command(BaseCommand):
    help = 'Ensure <ServiceName> product exists in database'

    def handle(self, *args, **options):
        product, created = Product.objects.get_or_create(
            title='서비스 제목',
            defaults={
                'lead_text': '매력적인 한 줄 문구',
                'description': '2~3문장 이상의 설명',
                'price': 0.00,
                'is_active': True,
                'icon': '🎨',
                'color_theme': 'purple',
                'card_size': 'small',
                'service_type': 'tool',
            }
        )
        # ProductFeature 최소 3개 등록 (SIS Rule)
```

```
```

        # [SIS Rule] ServiceManual 자동 생성 (Rich Content)
        from products.models import ServiceManual, ManualSection
        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={'title': f'{product.title} 사용법', 'is_published': True}
        )
        if manual.sections.count() == 0:
            ManualSection.objects.create(manual=manual, title='시작하기', content='...', display_order=1)
            ManualSection.objects.create(manual=manual, title='주요 기능', content='...', display_order=2)
            ManualSection.objects.create(manual=manual, title='활용 팁', content='...', display_order=3)

```
# Procfile 예시
web: python3 manage.py migrate --noinput && python3 manage.py ensure_ssambti && python3 manage.py ensure_studentmbti && ...
```

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
- [ ] **[Richness]** `ProductFeature`가 최소 3개 이상 등록되어 모달이 풍성해 보이는가?
- [ ] **[Manual]** `ServiceManual`과 최소 3개 이상의 `ManualSection`이 `ensure_` 커맨드를 통해 자동 생성되는가? (빈 껍데기만 있으면 안 됨)
- [ ] **[Terminology]** 학생을 대상으로 할 때 MBTI/검사 등 지루한 용어가 순화(캐릭터/찾기 등)되었는가?
- [ ] **[Auth]** 학생 참여 시 비로그인(Guest) 플로우가 원활한가?
- [ ] **[Infra]** 새로운 라이브러리를 사용했다면 `requirements.txt`에 버전과 함께 명시했는가?
- [ ] **[Infra]** `ensure_<app_name>` management command를 생성하고 **4곳 모두** 등록했는가? (`INSTALLED_APPS`, `Procfile`, `nixpacks.toml`, `run_startup_tasks()`) — 하나라도 누락 시 502 에러 또는 대시보드 미노출
- [ ] **[Infra]** `nixpacks.toml`의 `[phases.start]` 명령이 `Procfile`과 동기화되어 있는가? (불일치 시 배포 환경에 따라 다른 명령이 실행됨)

---
**이 가이드는 `eduitit`의 바이브를 유지하며 가장 빠르게 서비스를 출시하기 위한 약속입니다.**

## Addendum: Enterprise Implementation Learnings (2026-02-15)

### 1) Runtime and Deployment (MUST)
- Production runtime must be ASGI-compatible and startup commands must be consistent across deployment files.
- Startup sequence must be idempotent (`migrate`, cache table setup, ensure commands) and safe to rerun.
- Keep production DB pooler compatibility settings enabled.

### 2) Queue Strategy (MUST)
- Primary async job backend is DB queue.
- New services must define:
  - retry policy (max attempts + backoff)
  - failure state persistence (failed-job record)
  - reprocessing/repair workflow
- Do not introduce Redis-only assumptions unless explicitly approved.

### 3) AI Integration Reliability (MUST)
- All AI clients require explicit timeout and bounded retries.
- Circuit breaker must protect high-traffic AI paths.
- For generator/stream responses, success/failure must be recorded at the response-consumer boundary.

### 4) Error and Security Contract (MUST)
- User-facing responses must never include raw internal exception text.
- Health checks return stable status only (`ok`/`error`) without internals.
- Full diagnostics remain in logs/monitoring only.

### 5) Verification Standard (MUST)
- Minimum gate:
  - `python manage.py check`
  - service health test suite
  - syntax/compile check for changed Python modules
- Endpoint health tests must follow actual product access policy (public/auth redirect behavior).

### 6) Operational Readiness (SHOULD)
- Maintain pre-deploy and post-deploy smoke scripts.
- Track and alert on:
  - 5xx ratio
  - p95 latency
  - AI upstream error ratio
  - rate-limit rejection ratio
