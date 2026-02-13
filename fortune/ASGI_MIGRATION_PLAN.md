# Fortune 프로젝트 동시 처리 확장 계획: WSGI → ASGI 전환

## Context

현재 gunicorn gthread (3 workers × 4 threads = **동시 12개 요청**)으로 운영 중. AI API 호출(Gemini, DeepSeek)이 30~60초간 스레드를 점유하므로, 동시 사용자 12명이 한계. 근본 해결책은 **ASGI + async views 전환**으로, 이벤트 루프 기반으로 I/O 대기 중 스레드를 점유하지 않아 동일 리소스에서 **200~500+ 동시 요청** 처리 가능.

---

## 사전 발견: 현재 환경의 기존 문제

ASGI 전환과 무관하게 발견된 문제로, 먼저 수정해야 안정적 전환 가능:

1. **캐시 백엔드 미설정**: 현재 Django 기본 LocMemCache 사용 → 워커 간 캐시 공유 불가. Redis 필요
2. **Neon DB 설정 누락**: `DISABLE_SERVER_SIDE_CURSORS = True` 미설정 → PgBouncer와 충돌 가능

---

## 단계별 구현 계획 (각 단계별 영향 분석 + 롤백 포함)

### 0단계: 사전 준비 (기존 WSGI 환경에서 먼저 적용)

#### 0-1. Redis 캐시 백엔드 추가
- `requirements.txt`에 `django-redis` 추가
- Railway에 Redis 서비스 추가
- `settings_production.py`에 `CACHES` 설정 추가
- **영향**: 캐시 관련 코드만 영향. 기존 LocMemCache에서 Redis로 변경
- **롤백**: `CACHES` 설정 제거하면 자동으로 LocMemCache 복원

#### 0-2. Neon DB 설정 보완
- `settings_production.py`에 `DISABLE_SERVER_SIDE_CURSORS = True` 추가
- **영향**: DB 쿼리 방식 변경 (server-side cursor → client-side cursor). 대량 QuerySet 순회 시 메모리 사용 증가 가능하나, 현재 프로젝트에서 대량 데이터 처리 없으므로 무관
- **롤백**: 해당 설정 제거

---

### 1단계: DB 어댑터 교체 (psycopg2 → psycopg v3)

#### 변경 사항
- `requirements.txt`: `psycopg2-binary==2.9.10` → `psycopg[binary]>=3.1`

#### 영향 분석
- **Django ORM**: Django 6.0은 psycopg v3를 자동 감지, 동일한 `django.db.backends.postgresql` 엔진 사용. ORM API 변경 없음
- **dj-database-url**: 호환됨 (드라이버 레벨이므로 URL 파싱과 무관)
- **기존 쿼리**: 99% 호환. 극히 드문 raw SQL에서 `%s` placeholder 대신 psycopg3의 네이티브 `$1` 사용 가능하나, Django ORM이 자동 변환
- **conn_max_age=600**: psycopg v3에서도 동일하게 동작

#### 위험 요소
- psycopg v3는 psycopg2와 **import 경로가 다름** (`import psycopg` vs `import psycopg2`)
- 직접 `psycopg2`를 import하는 코드가 있으면 깨짐

#### 롤백
- `requirements.txt`에서 `psycopg[binary]` → `psycopg2-binary==2.9.10`으로 되돌리기
- 한 줄 변경으로 즉시 복원 가능

---

### 2단계: 서버 교체 (gunicorn/WSGI → uvicorn/ASGI)

#### 변경 사항
- `requirements.txt`에 추가: `uvicorn[standard]`, `uvloop`, `httptools`
- `requirements.txt`에서 `gunicorn==23.0.0`은 **제거하지 않고 유지** (롤백용)
- `config/asgi.py` 확인/수정
- `Procfile` 변경 (기존 명령 주석 보존):
  ```
  # ROLLBACK: gunicorn config.wsgi --workers 3 --threads 4 --worker-class gthread --timeout 120
  web: python3 manage.py migrate --noinput && ... && uvicorn config.asgi:application --host 0.0.0.0 --port $PORT --workers 2 --loop uvloop --http httptools --timeout-keep-alive 120
  ```
- `nixpacks.toml` start 명령도 동일하게 변경

#### 영향 분석
- **모든 기존 sync 뷰**: 그대로 동작. Django ASGI는 sync 뷰를 자동으로 threadpool에서 실행
- **미들웨어**:
  - `VisitorTrackingMiddleware`: DB write(`get_or_create`)가 있으나, sync 뷰와 함께 threadpool에서 실행되므로 문제 없음
  - `OnboardingMiddleware`: read-only, 안전
  - `MaintenanceModeMiddleware`: 설정값 체크만, 안전
  - `WhiteNoise`: v6.0+ ASGI 지원, 안전
  - `django-htmx`: 헤더 읽기만, 안전
- **django-allauth**: ASGI 호환 이슈 보고됨 (Issue #3566, #3969). 최신 버전(65.x+) 사용 필수. AccountMiddleware에서 async 뷰 취소 시 워커 프리즈 가능
- **django-ratelimit**: sync 뷰에서는 기존과 동일하게 동작 (이 단계에서는 async 뷰 없음)
- **signals** (`core/signals.py`): 파일 삭제 시그널 등 sync로 동작, threadpool에서 실행되므로 문제 없음
- **Session/CSRF**: Django 세션 미들웨어는 ASGI 인식, 정상 동작

#### 위험 요소
- **django-allauth AccountMiddleware**: 가장 큰 리스크. 인증 플로우 (로그인/회원가입/OAuth) 집중 테스트 필요
- **uvloop**: Windows에서 미지원 → 로컬 개발(Windows)에서는 `--loop uvloop` 제거 필요

#### 롤백 (즉시, 1분 이내)
```
# Procfile에서 주석 해제만 하면 됨:
web: ... && gunicorn config.wsgi --workers 3 --threads 4 --worker-class gthread --timeout 120
```
- gunicorn은 requirements에 남아있으므로 재설치 불필요
- Railway에서 Procfile 변경 후 재배포 = 약 2~3분

---

### 3단계: AI 뷰 async 전환 (핵심, 최대 효과)

**중요: 한 번에 하나씩 전환, 각 전환 후 배포 & 검증**

#### 전환 순서 (영향도 순):

##### 3-1. `saju_streaming_api()` (최우선)
- SSE 스트리밍으로 가장 오래 스레드 점유 (전체 응답 시간 동안)
- `StreamingHttpResponse`의 동기 generator → async generator로 변환
- AI 클라이언트: `OpenAI()` → `AsyncOpenAI()` / `client.aio.models.generate_content_stream()`
- **영향**: 이 뷰만 변경, 다른 뷰 무관
- **롤백**: `async def` → `def`로 되돌리기 (함수 시그니처 1줄 + 내부 await 제거)

##### 3-2. `saju_view()`
- POST 요청 → AI API 호출 → HTML 반환
- `await async_client.chat.completions.create(...)` 사용
- DB 저장: `Model.objects.create()` → `await Model.objects.acreate()`
- `render()` 래핑: `await sync_to_async(render)(...)`
- **영향**: 사주 메인 뷰만 변경
- **롤백**: 동일 (async → sync 복원)

##### 3-3. `daily_fortune_api()`, `analyze_topic()`
- 동일 패턴으로 전환
- 캐시 접근: `await sync_to_async(cache.get/set)(...)`

#### Rate Limit 처리
- async 뷰에서는 `@ratelimit` 데코레이터 대신 수동 체크:
  ```python
  from asgiref.sync import sync_to_async
  from ratelimit.utils import is_ratelimited

  async def saju_view(request):
      limited = await sync_to_async(is_ratelimited)(
          request, fn=saju_view, key='user', rate='10/m', increment=True
      )
      if limited:
          return HttpResponse('Rate limited', status=429)
  ```
- **영향**: rate limit 로직만 변경, 기존 제한 정책 동일 유지
- **롤백**: `@ratelimit` 데코레이터 복원

#### django-ratelimit의 `ratelimit_key_for_master_only` 콜백
- `core/utils.py`에서 `user.userprofile` 접근 → lazy loading 주의
- async 뷰에서는 `select_related('userprofile')`로 미리 로드 필요

#### 위험 요소
- **async/sync 혼용 실수**: async 뷰에서 동기 ORM 호출 시 `SynchronousOnlyOperation` 에러 → Sentry에서 즉시 감지 가능
- **AI SDK async 지원 확인 필요**: `google-genai`의 `client.aio` 인터페이스, `openai`의 `AsyncOpenAI` 둘 다 공식 지원

---

### 변환하지 않을 뷰 (sync 유지)

- django-allauth 뷰 (로그인, 회원가입, OAuth)
- Admin 뷰
- 100ms 이내 완료되는 단순 템플릿 렌더링 뷰
- `@transaction.atomic` 사용 뷰 (async transaction 미지원)
- 파일 업로드 뷰 (collect, autoarticle) — 추후 별도 최적화

---

## 수정 대상 파일

| 파일 | 변경 내용 | 단계 |
|------|-----------|------|
| `requirements.txt` | +django-redis, psycopg2→psycopg, +uvicorn/uvloop/httptools | 0~2 |
| `config/settings_production.py` | CACHES(Redis), DISABLE_SERVER_SIDE_CURSORS | 0 |
| `Procfile` | gunicorn → uvicorn (기존 명령 주석 보존) | 2 |
| `nixpacks.toml` | start 명령 변경 | 2 |
| `config/asgi.py` | ASGI 엔트리포인트 확인 | 2 |
| `fortune/views.py` | 4개 AI 뷰를 async로 전환 | 3 |
| `core/utils.py` | ratelimit 콜백 async 호환 | 3 |

---

## 예상 효과

| 구성 | 동시 I/O 요청 |
|------|---------------|
| **현재**: gunicorn gthread 3w×4t | **12개** |
| **0~2단계 후**: uvicorn ASGI (sync 뷰 유지) | **~30개** (threadpool 기본 40 스레드) |
| **3단계 완료**: uvicorn ASGI + async AI 뷰 | **200~500+개** |

---

## 롤백 전략 요약

| 단계 | 롤백 방법 | 소요 시간 |
|------|-----------|-----------|
| 0단계 (Redis/DB설정) | 설정 라인 제거 | 재배포 3분 |
| 1단계 (psycopg) | requirements.txt 1줄 변경 | 재배포 3분 |
| 2단계 (uvicorn) | Procfile 주석 토글 | 재배포 3분 |
| 3단계 (async 뷰) | 각 뷰 함수를 sync로 복원 | git revert + 재배포 5분 |
| **전체 롤백** | git revert로 이전 커밋 복원 | 재배포 3분 |

**핵심 원칙**: 각 단계를 별도 커밋으로 관리하여, 문제 발생 시 해당 커밋만 revert

---

## 검증 체크리스트

### 각 단계 배포 후:
- [ ] 메인 페이지 정상 로딩
- [ ] 로그인/회원가입/카카오 OAuth 정상 동작
- [ ] 사주 분석 요청 정상 응답
- [ ] SSE 스트리밍 정상 수신
- [ ] Rate limit 정상 동작
- [ ] Sentry에 `SynchronousOnlyOperation` 에러 없음
- [ ] Railway 로그에 에러 없음

### 최종 검증:
- [ ] 동시 20+ 사용자 테스트 (부하 테스트)
- [ ] AI API 타임아웃 시 에러 핸들링 정상
- [ ] 캐시 히트율 확인 (Redis 모니터링)
