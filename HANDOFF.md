# Handoff: 홈페이지 V2 UX 리디자인 Phase 1

**날짜**: 2026-02-17
**상태**: Phase 1 구현 완료 (커밋 `8007741`)
**플래그**: `HOME_V2_ENABLED=False` (기본 꺼짐)

---

## 완료된 작업

### 구현 완료 항목

| # | 항목 | 파일 | 상태 |
|---|------|------|------|
| 1 | Feature Flag `HOME_V2_ENABLED` | `config/settings.py`, `config/settings_production.py` | ✅ |
| 2 | Product 모델 필드 (`solve_text`, `result_text`, `time_text`) | `products/models.py` | ✅ |
| 3 | Admin에 새 필드 노출 (collapsible) | `products/admin.py` | ✅ |
| 4 | 데이터 마이그레이션 + idempotent 백필 | `products/migrations/0032_add_v2_home_fields.py` | ✅ |
| 5 | `PURPOSE_SECTIONS` 매핑 + `get_purpose_sections()` | `core/views.py` | ✅ |
| 6 | `_home_v2()` 뷰 함수 + `home()` flag 분기 | `core/views.py` | ✅ |
| 7 | 목적별 섹션 컴포넌트 | `core/includes/purpose_sections.html` | ✅ |
| 8 | 미니 카드 컴포넌트 (`openModal` 호출) | `core/includes/mini_card.html` | ✅ |
| 9 | 게임 배너 컴포넌트 | `core/includes/game_banner.html` | ✅ |
| 10 | 로그인 V2 홈 (인사말 + 퀵액션 + 섹션 + 게임 + 전체보기 토글) | `core/home_authenticated_v2.html` | ✅ |
| 11 | 비로그인 V2 홈 (Hero + 섹션 + CTA + 전체보기 토글) | `core/home_v2.html` | ✅ |
| 12 | 클릭 계측 (`data-track` / `data-track-label`) | V2 템플릿 내 JS | ✅ |
| 13 | `python manage.py check` 통과 | - | ✅ |

### 기존 파일 무수정 확인
- `home.html`, `home_authenticated.html`, `card_product.html`, `base.html`, `sns_widget.html`, `sns_widget_mobile.html` — 변경 없음

---

## 아직 구현 안 된 것들

### Phase 1 잔여 (배포 전 확인 필요)

| # | 항목 | 설명 | 우선도 |
|---|------|------|--------|
| 1 | **프로덕션 데이터 백필 확인** | 마이그레이션이 프로덕션 DB에 적용되면 title 매칭 여부 확인 필요. 프로덕션 Product title이 백필 딕셔너리와 다르면 solve_text가 비어있을 수 있음 → Admin에서 수동 입력 또는 title 수정 | 높음 |
| 2 | **퀵 액션 URL 직접 이동** | 현재 `external_url` 있으면 직접 이동, 없으면 `openModal()` 호출. 일부 서비스는 `preview_modal.html`의 시작 버튼 분기에 의존 → 퀵 액션에서 모달 거치지 않고 바로 서비스 URL로 이동하려면 각 서비스별 URL 매핑 필요 | 중간 |
| 3 | **반응형 360px 검증** | 360px 모바일에서 목적별 섹션 1열 표시, 퀵액션 가로 스크롤 정상 동작 확인 필요 | 높음 |
| 4 | **내부 계정 테스트** | Railway에서 `HOME_V2_ENABLED=True` 설정 후 superuser로 먼저 테스트 | 높음 |

### Phase 2: Ctrl+K 전역 검색 모달 (미착수)

| # | 항목 | 설명 |
|---|------|------|
| 1 | 검색 모달 UI | `Ctrl+K` 또는 `/` 키로 열리는 검색 모달 |
| 2 | 서비스 검색 | Product title, description, solve_text 기반 실시간 필터링 |
| 3 | 키보드 네비게이션 | 화살표 키 + Enter로 서비스 선택/이동 |
| 4 | 최근 검색 기록 | localStorage 기반 최근 검색어 5개 |

### Phase 3: 개인화 (미착수)

| # | 항목 | 설명 |
|---|------|------|
| 1 | 최근 사용 서비스 | `UserServiceLog` 모델 → 최근 사용 3개 표시 |
| 2 | 즐겨찾기 | 별표 토글 → `UserFavoriteProduct` 모델 |
| 3 | 역할 기반 추천 | `UserProfile.role`에 따라 퀵 액션 자동 정렬 (학교 → 수업 도구 우선, 강사 → 행정 도구 우선) |
| 4 | 퀵 액션 usage 기반 전환 | Phase 1의 `is_featured` 기반 → usage 빈도 기반으로 교체 |

### Phase 4: 온보딩 가이드 (미착수)

| # | 항목 | 설명 |
|---|------|------|
| 1 | "3분 시나리오" 카드 | 신규 사용자에게 서비스 활용 시나리오 3개 제시 |
| 2 | 진행률 표시 | 온보딩 완료율 프로그레스 바 |
| 3 | 스킵 가능 | "다시 보지 않기" 체크박스 → `UserProfile.onboarding_done` |

---

## 배포 순서

1. **현재**: 코드 배포 완료 + `HOME_V2_ENABLED=False` (기존 홈 100%)
2. **다음**: Railway에서 `HOME_V2_ENABLED=True` → superuser로 테스트
3. **이후**: 문제 없으면 전체 오픈
4. **롤백**: `HOME_V2_ENABLED=False` 환경변수 1줄로 즉시 복구

---

## 관련 파일 목록

| 파일 | 역할 |
|------|------|
| `config/settings.py` | `HOME_V2_ENABLED` flag |
| `config/settings_production.py` | `HOME_V2_ENABLED` flag (동기화) |
| `core/views.py` | `PURPOSE_SECTIONS`, `get_purpose_sections()`, `_home_v2()`, `home()` flag 분기 |
| `products/models.py` | `solve_text`, `result_text`, `time_text` 필드 |
| `products/admin.py` | V2 필드 Admin 노출 |
| `products/migrations/0032_add_v2_home_fields.py` | 스키마 + 백필 마이그레이션 |
| `core/templates/core/includes/purpose_sections.html` | 목적별 4개 섹션 루프 |
| `core/templates/core/includes/mini_card.html` | 미니 서비스 카드 |
| `core/templates/core/includes/game_banner.html` | 게임 배너 |
| `core/templates/core/home_authenticated_v2.html` | 로그인 V2 홈 |
| `core/templates/core/home_v2.html` | 비로그인 V2 홈 |

---

---

# Handoff: ASGI 전환 후 사주 분석 오류 디버깅

**날짜**: 2026-02-15
**상태**: 디버깅 진행 중 (서버 로그 확인 필요)

---

## 현재 상황

엔터프라이즈급 인프라 전환(14단계) 완료 후 배포했으나, **사주 분석 기능이 깨짐**.

### 증상
- 사주 분석 시 "선생님, 잠시 AI와의 연결이 불안정했어요" 에러 표시
- 캐시된 결과(DB에 이미 있는 FortuneResult)도 불러오지 못함
- 에러 위치: `fortune/templates/fortune/saju_form.html:2856` JS catch 블록 (프론트엔드 catch-all)
- JS는 `fetch('{% url "fortune:saju_api" %}')` → `saju_api_view` (async) 호출

### 유지보수 모드
- `MAINTENANCE_MODE=true` 설정됨 (Railway 환경변수)
- superuser만 접속 가능
- 대소문자 무관하게 동작하도록 수정 완료 (`.lower() in ('true', '1', 'yes')`)

---

## 배포된 변경사항 요약

| 변경 | 이전 | 이후 |
|------|------|------|
| DB 어댑터 | psycopg2-binary | psycopg[binary]>=3.1 |
| 서버 | Gunicorn gthread 3w×4t | Uvicorn 2 workers + uvloop |
| 프로토콜 | WSGI | ASGI |
| AI 뷰 | 동기 | async (saju_api_view, saju_streaming_api, daily_fortune_api, analyze_topic, send_chat_message) |
| 캐시 | LocMemCache | Django DatabaseCache |
| Rate limit | block=False | block=True |
| 신규 | - | Circuit Breaker, Health Check, CSP 재활성화 |

---

## 에러 흐름 추적

```
[사용자] 사주 폼 제출
  ↓
[JS] fetch('/fortune/api/') POST → saju_api_view (async)
  ↓
[서버 처리 순서]
  1. await _check_saju_ratelimit(request)     ← ⚠️ 캐시 테이블 없으면 여기서 실패
  2. SajuForm(request.POST) 검증
  3. await sync_to_async(get_chart_context)(data)  ← ⚠️ psycopg v3 이슈면 여기서 실패
  4. await FortuneResult.objects.filter(...).afirst()  ← DB 캐시 조회
  5. await _collect_ai_response(prompt, request)     ← AI 호출 (캐시 없을 때만)
  ↓
[서버] except Exception → JsonResponse(status=500, 'AI_ERROR')
  ↓
[JS] response.ok === false → throw → catch → "AI와의 연결이 불안정했어요"
```

---

## 디버깅 진행 상황

### 확인 완료 (문제 아닌 것)
- `Stem.element`는 CharField → async 접근 시 SynchronousOnlyOperation 없음
- `config/asgi.py` 정상
- `CACHES` 설정 정상 (DatabaseCache + `django_cache_table`)
- `DISABLE_SERVER_SIDE_CURSORS = True` 설정됨
- `Procfile`에 `createcachetable` 포함
- `@login_required` + `@csrf_exempt` on async view: Django 6.0 지원됨
- superuser는 rate limit 안 걸림 (`fortune_rate_h` → `None`)
- `saju_view` (동기 폼 렌더링 뷰)는 변경 없음, 정상 동작

### 확인 필요 (우선순위 순)

#### 1. Railway 서버 로그 / Sentry 에러 확인 ★최우선★
```
검색 키워드: "사주 API 전역 오류" 또는 "SynchronousOnlyOperation" 또는 "ProgrammingError"
```
- `saju_api_view`의 `except Exception as e` 블록이 `logger.exception()` 로그 남김
- Sentry에서 fortune 관련 500 에러 검색

#### 2. createcachetable 실행 여부
- `is_ratelimited()` → `cache.get()`/`cache.set()` → `django_cache_table` 필요
- 테이블 없으면 `ProgrammingError` → `_check_saju_ratelimit`에서 즉시 실패
- **확인 방법**: Railway 쉘에서 `python manage.py dbshell` → `\dt django_cache_table`

#### 3. psycopg v3 호환성
- `dj-database-url==2.3.0`이 `ENGINE: django.db.backends.postgresql` 설정
- Django 6.0이 psycopg v3 자동 감지
- `calculator.get_pillars(dt)` 내부 Stem/Branch 모델 조회가 실패할 수 있음

#### 4. Circuit Breaker 상태
- 배포 직후 초기 실패 → circuit breaker 열림 → 30초간 AI 차단
- 하지만 캐시된 결과는 AI 호출 안 하므로 무관해야 함
- 30초 후 half-open으로 자동 복구

#### 5. sync_to_async DB 커넥션
- Uvicorn + psycopg v3 + ThreadPoolExecutor 조합에서 커넥션 풀 이슈 가능
- Neon(PgBouncer) + thread별 새 커넥션 → 풀 소진 가능성

---

## 다음 단계

1. **Railway Logs 또는 Sentry에서 실제 Python traceback 확인**
2. traceback에 따라 수정:

| 에러 | 수정 방법 |
|------|-----------|
| `ProgrammingError: relation "django_cache_table"` | `python manage.py createcachetable` 재실행 |
| `SynchronousOnlyOperation` | 해당 ORM 호출에 `sync_to_async` 래핑 |
| psycopg 관련 에러 | `requirements.txt`에서 `psycopg2-binary` 복귀 |
| Circuit breaker 차단 | 재배포로 리셋 (in-memory 상태) |

3. 수정 후 사주 분석 테스트
4. 정상 확인 → `MAINTENANCE_MODE` 해제 (Railway 환경변수 삭제)

---

## 롤백 방법 (최후 수단)

```bash
# 1. Procfile: uvicorn → gunicorn 복귀 (주석 토글)
# ROLLBACK 주석 해제, uvicorn 라인 주석 처리

# 2. requirements.txt: psycopg v3 → psycopg2 복귀
# psycopg[binary]>=3.1 → psycopg2-binary==2.9.10

# 3. async 뷰 전환 커밋 git revert (필요 시)
```

---

## 관련 파일

| 파일 | 역할 |
|------|------|
| `fortune/views.py:389` | `saju_api_view` (async) - 에러 발생 뷰 |
| `fortune/views.py:215` | `_async_stream_ai` - async AI 스트리밍 래퍼 |
| `fortune/views.py:228` | `_collect_ai_response` - sync_to_async AI 수집 |
| `fortune/views.py:199` | `_check_saju_ratelimit` - async rate limit 체크 |
| `fortune/views.py:57` | `generate_ai_response` - AI 호출 (동기) |
| `fortune/api_views.py` | `analyze_topic` (async) |
| `fortune/views_chat.py` | `send_chat_message` (async) |
| `fortune/utils/chat_ai.py` | AsyncOpenAI 스트리밍 |
| `fortune/utils/circuit_breaker.py` | SimpleCircuitBreaker |
| `fortune/templates/fortune/saju_form.html:2725` | JS fetch 호출 |
| `fortune/templates/fortune/saju_form.html:2856` | JS 에러 catch 블록 |
| `config/settings_production.py:194` | CACHES (DatabaseCache) |
| `Procfile` | uvicorn + createcachetable |
| `requirements.txt:10` | psycopg[binary]>=3.1 |

---

## 플랜 파일 위치
- 전체 전환 계획: `C:\Users\kakio\.claude\plans\federated-meandering-harp.md`
- 기존 ASGI 마이그레이션 계획: `fortune/ASGI_MIGRATION_PLAN.md`

---

# Handoff: 운영 사이트 진단 & CLAUDE.md 보완

**날짜**: 2026-02-15
**상태**: 완료

---

## 수행 내용

6축 체크리스트(UI일관성, 접근성, 프론트구조, 성능, 운영유지, 보안)로 프로젝트를 진단하고, 부족한 영역을 `settings_production.py`와 `CLAUDE.md`에 보완함.

### 변경 파일 및 내역

| 파일 | 작업 | 상태 |
|------|------|------|
| `config/settings_production.py` | LOGGING 설정 추가 (settings.py와 동기화) | 완료 |
| `config/settings_production.py` | 쿠키 보안 4줄 추가 (`SESSION_COOKIE_HTTPONLY`, `CSRF_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE`, `CSRF_COOKIE_SAMESITE`) | 완료 |
| `CLAUDE.md` UI 레이아웃 섹션 | 반응형 브레이크포인트 표 추가 (Tailwind sm/md/lg/xl) | 완료 |
| `CLAUDE.md` #66 | 접근성(A11y) 필수 규칙 — 모달 키보드, 포커스 스타일, 색 대비, alt 텍스트, 체크리스트 | 완료 |
| `CLAUDE.md` #67 | 이미지 최적화 규칙 — lazy-load, Cloudinary f_auto,q_auto, `|optimize` 필터 참조 | 완료 |
| `CLAUDE.md` #68 | 정적 파일 캐시 버스팅 로드맵 (향후: WhiteNoise CompressedManifest) | 완료 |
| `CLAUDE.md` #69 | Tailwind CDN → 빌드 전환 로드맵 (Phase 1 병행, Phase 2 CDN 제거) | 완료 |

### 이미 충족되어 있던 항목 (변경 불필요)
- 규칙 #1의 "특히 주의할 설정"에 `LOGGING`이 이미 포함되어 있음
- 프로덕션 보안 헤더 (HSTS, SSL Redirect, X-Frame-Options 등) 이미 설정됨
- CSP (Content Security Policy) django-csp 미들웨어로 이미 적용됨
- Cloudinary 최적화 템플릿 태그 (`|optimize`, `|thumbnail`) 이미 구현됨

### 검증
- `python manage.py check` — 0 issues
- `settings_production.py` — Python 구문 검증 통과

### 보완으로 채운 Gap 3가지
1. **접근성(A11y)** — 강제 체크리스트 기반 규칙 신설 (#66)
2. **이미지/성능 최적화** — lazy-load + Cloudinary 전역 규칙 (#67)
3. **프로덕션 안전성** — LOGGING 동기화 + 쿠키 보안 명시 (settings_production.py)
