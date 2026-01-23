# 📂 Service Integration Master Plan: Yut, Saju, PlayAura

> **목적**: `eduitit` Django 프로젝트의 컨텍스트를 재로딩하지 않고, 외부 서비스(윷놀이, 사주, PlayAura)를 빠르고 정확하게 이식(Porting)하기 위한 참조 문서 및 실행 계획입니다.

## 1. 🏗️ Project Context (Read-Only Reference)

이 섹션은 현재 프로젝트의 핵심 구조를 요약합니다. AI는 이 정보를 참조하여 기존 코드와 일관성 있는 코드를 생성해야 합니다.

### **A. Tech Stack & Environment**
* **Framework**: Django 6.0.1, Python 3.x
* **Database**: SQLite (Development)
* **Deployment**: Railway / Render (Production settings exist)
* **Language**: Korean (`ko-kr`), Timezone: `Asia/Seoul`
* **Base Template**: `core/templates/base.html` (Bootstrap/Tailwind 기반 추정)

### **B. Core Application Structure (`config/settings.py`)**
* **Installed Apps**:
    * `core`: 기본 페이지 및 대시보드
    * `products`: 제품/서비스 관리 (윷놀이 포함)
    * `fortune`: 운세/사주 서비스 (Gemini API 연동)
    * `insights`, `portfolio`, `autoarticle`: 기타 기능
* **Authentication**: Django Standard Auth + `UserOwnedProduct` 모델로 접근 제어

### **C. Key Routing (`config/urls.py`)**
```python
urlpatterns = [
    path('', include('core.urls')),
    path('products/', include('products.urls')),  # 윷놀이 경로 포함
    path('fortune/', include('fortune.urls')),    # 사주 경로 포함
    # ... 기타 앱
]
D. Data Models Schema (Reference)
1. products.models.Product

서비스나 도구를 등록하는 메인 모델.

Fields: title, description, price, icon, color_theme, service_type (game, tool 등)

Usage: 윷놀이, PlayAura 등은 이 모델에 레코드로 등록되어야 함.

2. products.models.UserOwnedProduct

사용자가 구매/소유한 서비스 매핑.

Usage: 특정 서비스(예: 유료 사주, PlayAura 프리미엄) 접근 권한 체크 시 사용.

2. 🎯 Service Porting Specifications
각 서비스별 이식 현황과 목표입니다.

Service 1: 윷놀이 (Yut Nori)
Target App: products

Current Status:

View: yut_game (products/views.py)

URL: /products/yut/

Assets: static/products/yut/ (mp3 files exist)

Template: products/templates/products/yut_game.html

Porting Goal:

단순 HTML 렌더링을 넘어 게임 로직(JS) 완전 이식.

Product 모델과 연동하여 "게임 실행" 버튼으로 접근하도록 UX 개선.

Service 2: 사주 (Saju / Fortune)
Target App: fortune

Current Status:

View: saju_view, saju_api_view (fortune/views.py)

URL: /fortune/

Logic: Gemini API (gemini-3-flash-preview) 연동 완료.

Form: SajuForm

Porting Goal:

결과 페이지 UI 개선 (마크다운 렌더링 최적화).

API 키 오류 처리 및 로딩 상태 UX 강화.

Service 3: PlayAura (New Integration)
Target App: products (Tool/Service type) OR New App playaura

Porting Goal:

결정 필요: 기존 products 앱 내의 뷰로 구현할지, 별도 앱으로 분리할지 결정. (권장: products 내 기능으로 시작 후 필요 시 분리)

기존 PlayAura 소스 코드를 eduitit 스타일(Django View + Template)로 변환.

Product 모델에 "PlayAura" 등록 및 접근 권한 설정.

3. 🚀 Implementation Plan (Terminal-First)
"claude.md"의 터미널 중심 개발 방식을 따릅니다. 브라우저 확인은 최소화하고 테스트 코드로 검증합니다.

Phase 1: 윷놀이(Yut) 기능 고도화
[ ] TC-1: products/yut/ 접근 시 상태 코드 200 확인 테스트 (Pytest).

[ ] Dev: yut_game.html에 기존 JS 게임 로직 이식 및 정적 파일 경로({% static %}) 수정.

[ ] UI: 모바일 반응형 레이아웃 조정 (기존 base.html 상속 확인).

Phase 2: 사주(Saju) 서비스 안정화
[ ] TC-2: Gemini API 키 누락 시 예외 처리 로직 테스트.

[ ] Dev: fortune/views.py의 프롬프트 로직을 별도 모듈로 분리하여 관리 용이성 확보.

[ ] UI: 결과 화면에 "다시 보기", "저장하기" 등의 편의 기능 추가.

Phase 3: PlayAura 이식 (New)
[ ] Setup: PlayAura 관련 정적 파일(JS, CSS) static/playaura/로 이동.

[ ] Model: Product 모델에 PlayAura 항목 추가 (Admin 혹은 Data Migration).

[ ] View: products/views.py에 play_aura_view 추가.

[ ] URL: products/urls.py에 path 연결.

[ ] Test: 뷰 렌더링 및 핵심 기능 단위 테스트 작성.

4. 📝 Development Commands (Cheat Sheet)
Server Run: python manage.py runserver

Test Run: pytest or python manage.py test

Make Migrations: python manage.py makemigrations -> python manage.py migrate

Static Collect: python manage.py collectstatic

For AI Assistant:

위 Context를 바탕으로 추가 질문 없이 즉시 코드를 생성하세요.

기존 config, core, products 앱의 코딩 스타일을 유지하세요.

수정이 필요한 경우, 전체 파일 대신 수정된 블록이나 diff를 제공하세요.

### 💡 사용 가이드
1.  위 내용을 복사해서 `docs/plans/PLAN_integrated_services.md` (폴더가 없다면 만드세요)에 저장합니다.
2.  이후 작업을 요청할 때 **"PLAN_integrated_services.md 파일을 읽고 Phase 1(윷놀이)부터 작업을 진행해줘"**라고만 하면 됩니다.
3.  PlayAura의 경우, 구체적인 기존 코드가 있다면 Phase 3 단계에서 해당 코드 파일만 추가로 업로드해주면 됩니다.