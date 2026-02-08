# 김재현의 Claude Code 설정

## 개인 정보
- 이름: 김재현 (Jaehyun Kim)
- GitHub: jh941213
- 회사: KTDS

## 핵심 마인드셋
**Claude Code는 시니어가 아니라 똑똑한 주니어 개발자다.**
- 작업을 작게 쪼갤수록 결과물이 좋아진다
- "인증 기능 만들어줘" ❌
- "로그인 폼 만들고, JWT 생성하고, 리프레시 토큰 구현해줘" ✅

## 프롬프팅 베스트 프랙티스

### 1. Plan 모드 먼저 (가장 중요!)
```
Shift+Tab → Plan 모드 토글
복잡한 작업은 Plan 모드에서 계획 → 확정 후 구현
```

### 2. 구체적인 프롬프트
```
❌ "버튼 만들어줘"
✅ "파란색 배경에 흰 글씨, 호버하면 진한 파란색,
    클릭하면 /auth/login API 호출하는 버튼 만들어줘.
    이 버튼은 로그인 폼에 들어가."
```

### 3. 에이전트 체이닝
```
복잡한 작업 → /plan → 구현 → /review → /verify
```

## 컨텍스트 관리 (핵심!)

**컨텍스트는 신선한 우유. 시간이 지나면 상한다.**

### 규칙
- 토큰 80-100k 넘기 전에 리셋 (200k 가능하지만 품질 저하)
- 3-5개 작업마다 컨텍스트 정리
- /compact 3번 후 /clear

### 컨텍스트 관리 패턴
```
작업 → /compact → 작업 → /compact → 작업 → /compact
→ /handoff (HANDOFF.md 생성) → /clear → 새 세션
```

### HANDOFF.md 필수!
컨텍스트 리셋 전에 반드시 HANDOFF.md 생성
- 지금까지 뭐 했는지
- 다음에 뭐 해야 하는지
- 주의할 점

## 사용 가능한 커맨드
| 커맨드 | 용도 |
|--------|------|
| `/plan` | 작업 계획 수립 |
| `/frontend` | 빅테크 스타일 UI 개발 (플래닝→구현) |
| `/commit-push-pr` | 커밋→푸시→PR 한 번에 |
| `/verify` | 테스트, 린트, 빌드 검증 |
| `/review` | 코드 리뷰 |
| `/simplify` | 코드 단순화 |
| `/tdd` | 테스트 주도 개발 |
| `/build-fix` | 빌드 에러 수정 |
| `/handoff` | HANDOFF.md 생성 |
| `/compact-guide` | 컨텍스트 관리 가이드 |

## 사용 가능한 에이전트
| 에이전트 | 용도 |
|----------|------|
| `planner` | 복잡한 기능 계획 |
| `frontend-developer` | 빅테크 스타일 UI 구현 (React/TS/Tailwind) |
| `code-reviewer` | 코드 품질/보안 리뷰 |
| `architect` | 아키텍처 설계 |
| `security-reviewer` | 보안 취약점 분석 |
| `tdd-guide` | TDD 방식 안내 |

## MCP 관리 규칙
- MCP 서버 20-30개 설정 가능
- 실제 활성화는 10개 미만 유지
- 전체 도구 수 80개 미만 (너무 많으면 느려짐)
- 프로젝트마다 필요한 MCP만 활성화

## 코딩 스타일
- 한국어로 주석과 커밋 메시지 작성
- 코드는 간결하고 읽기 쉽게
- 불변성 패턴 사용 (뮤테이션 금지)
- 함수 50줄 이하, 파일 800줄 이하

## 자주 사용하는 명령어
```bash
npm run build    # 빌드
npm test         # 테스트
npm run lint     # 린트
```

## 금지 사항
- main/master 브랜치에 직접 push 금지
- .env 파일이나 민감한 정보 커밋 금지
- 하드코딩된 API 키/시크릿 금지
- console.log 커밋 금지

## 선호하는 기술 스택
- Frontend: React, TypeScript, Next.js
- Backend: Node.js, Python
- Database: PostgreSQL, MongoDB

## 커밋 메시지 형식
```
[타입] 제목

본문 (선택)

Co-Authored-By: Claude <noreply@anthropic.com>
```
타입: feat, fix, docs, style, refactor, test, chore

## 작업 완료 후 체크리스트
- [ ] 테스트 통과
- [ ] 린트 통과
- [ ] 타입 체크 통과
- [ ] console.log 제거
- [ ] 보안 검토 (API 키, 시크릿)

## 설치된 스킬 (~/.agents/skills/)

### Frontend (7개)
| 스킬 | 용도 |
|------|------|
| `vercel-react-best-practices` | React/Next.js 성능 패턴 |
| `react-patterns` | React 디자인 패턴 |
| `typescript-advanced-types` | 고급 타입 시스템 |
| `shadcn-ui` | 커스텀 컴포넌트 |
| `tailwind-design-system` | Tailwind 시스템 |
| `ui-ux-pro-max` | UX 종합 가이드 |
| `web-design-guidelines` | UI 가이드라인/리뷰 |

### Backend - FastAPI/Python (4개)
| 스킬 | 용도 |
|------|------|
| `fastapi-templates` | FastAPI 템플릿/패턴 |
| `api-design-principles` | REST API 설계 원칙 |
| `async-python-patterns` | Python 비동기 패턴 |
| `python-testing-patterns` | Python 테스트 패턴 |

### 워크플로우
```
# 프론트엔드
/frontend [요청사항] → frontend-developer 에이전트 → /verify

# 백엔드는 일반 플래닝 사용
/plan [요청사항] → 구현 → /verify
```

## Claude가 자주 실수하는 것 (여기에 추가)
<!-- Claude가 실수할 때마다 여기에 규칙 추가 -->

### ⚠️ Django 설정 파일 동기화 (중요!)

**문제 상황**:
- 로컬에서는 작동하는데 프로덕션(Railway/Heroku)에서 안 되는 경우
- 특히 미들웨어, context processor, INSTALLED_APPS 등 설정 관련

**원인**:
```
로컬: config/settings.py 사용
프로덕션: config/settings_production.py 사용 (wsgi.py에서 지정)
```

**해결 규칙**:
1. **Django에서 기능 추가 시 반드시 체크**:
   - `settings.py`에 추가했으면
   - `settings_production.py`에도 동일하게 추가

2. **특히 주의할 설정들**:
   - `MIDDLEWARE` - 미들웨어 추가 시
   - `INSTALLED_APPS` - 앱 추가 시
   - `TEMPLATES['OPTIONS']['context_processors']` - context processor 추가 시
   - `LOGGING` - 로깅 설정 변경 시

3. **확인 방법**:
   ```bash
   # 두 파일 비교
   diff config/settings.py config/settings_production.py
   ```

**실제 사례 (2026-02-02)**:
- 방문자 카운터가 10번 넘게 수정해도 0명
- 코드는 완벽, 로컬에서 정상 작동
- 문제: `settings_production.py`에 미들웨어/context processor 누락
- 해결: 두 설정 파일 동기화

**베스트 프랙티스**:
- 공통 설정은 `settings_base.py`로 분리
- 환경별 차이만 각 설정 파일에 작성
- 또는 settings.py 하나만 사용하고 환경변수로 분기

---

### ⚠️ Django views.py 필수 체크리스트 (2026-02-04)

**증상**: 500 Internal Server Error (로컬/프로덕션 모두)

**흔한 실수 3가지**:

1. **settings import 누락**
   ```python
   # ❌ 잘못된 코드
   def my_view(request):
       return render(request, 'template.html', {
           'KAKAO_KEY': settings.KAKAO_JS_KEY  # NameError!
       })

   # ✅ 올바른 코드
   from django.conf import settings  # 반드시 추가!

   def my_view(request):
       return render(request, 'template.html', {
           'KAKAO_KEY': settings.KAKAO_JS_KEY
       })
   ```

2. **변수 정의 순서 문제**
   ```python
   # ❌ 잘못된 코드
   def my_view(request):
       theme = MBTI_COLORS.get('ISTJ')  # NameError: MBTI_COLORS not defined

   MBTI_COLORS = {  # 함수보다 아래에 정의
       'ISTJ': '#3B82F6',
   }

   # ✅ 올바른 코드
   MBTI_COLORS = {  # 상수는 파일 상단에 먼저 정의
       'ISTJ': '#3B82F6',
   }

   def my_view(request):
       theme = MBTI_COLORS.get('ISTJ')
   ```

3. **함수에서 return 문 누락**
   ```python
   # ❌ 잘못된 코드
   def my_view(request):
       context = {'data': 'test'}
       # return 없음! → None 반환 → 500 에러

   # ✅ 올바른 코드
   def my_view(request):
       context = {'data': 'test'}
       return render(request, 'template.html', context)
   ```

**실제 사례 (ssambti 앱)**:
- 증상: ssambti 페이지 접속 시 500 에러
- 원인 1: `from django.conf import settings` 누락
- 원인 2: `card_generator_view()`가 `MBTI_COLOR_THEMES` 정의 전에 위치
- 원인 3: `card_generator_view()`에 return 문 없음
- 해결: import 추가 + 함수 순서 재배치 + return 문 추가

**체크리스트**:
- [ ] 필요한 모든 import 확인 (`settings`, `models`, 외부 라이브러리)
- [ ] 상수/딕셔너리는 파일 상단에 정의
- [ ] 모든 view 함수에 `return` 문 있는지 확인
- [ ] `python manage.py check <앱이름>` 실행하여 검증

---

### ⚠️ Railway 배포 환경 제약사항 (2026-02-08)

**Railway 컨테이너에는 시스템 도구가 제한적이다.**

1. **`pg_dump` 없음** — `django-dbbackup`처럼 외부 DB 클라이언트가 필요한 패키지는 작동하지 않음
   - 해결: Django 내장 `dumpdata`로 JSON 백업 (`core/management/commands/backup_db.py`)
   - `pg_dump`이 필요하면 `nixpacks.toml`의 `nixPkgs`에 `"postgresql"` 추가 필요

2. **Neon PostgreSQL = PgBouncer (transaction pooling mode)**
   - 서버사이드 커서 사용 불가 → `dumpdata` 등 대량 쿼리 시 `cursor does not exist` 에러
   - 해결: `connections['default'].settings_dict['DISABLE_SERVER_SIDE_CURSORS'] = True`
   - 또는 settings에 전역으로 설정: `DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True`

3. **Railway Cron Job은 별도 컨테이너**
   - 메인 웹 서비스와 다른 컨테이너에서 실행됨
   - management command에서 `raise` 대신 `sys.exit(0/1)` 사용해야 성공/실패 상태가 정확히 전달됨
   - startup task(ensure_ssambti 등)와 로그가 섞일 수 있음

4. **새 Python 패키지 추가 시 반드시 확인할 것**:
   - `requirements.txt`에 추가 (즉시!)
   - 해당 패키지가 시스템 바이너리에 의존하는지 확인 (예: `pg_dump`, `wkhtmltopdf` 등)
   - 시스템 바이너리가 필요하면 `nixpacks.toml`의 `nixPkgs`에 추가
   - `Procfile` ↔ `nixpacks.toml` start 명령어 동기화 확인

---

### ⚠️ 서비스 인프라 구조 참고 (2026-02-08)

**현재 구현된 서비스 핵심 기능:**

| 기능 | 파일 | 비고 |
|------|------|------|
| Toast 알림 | `core/context_processors.py` → `toast_messages()` | Django messages + Alpine.js |
| 글로벌 배너 | `core/models.py` → `SiteConfig` (싱글톤) | Admin에서 관리 |
| SEO 메타태그 | `core/context_processors.py` → `seo_meta()` | view context로 override 가능 |
| 피드백 위젯 | `core/models.py` → `Feedback`, `/feedback/` | HTMX + 플로팅 버튼 |
| 관리자 대시보드 | `/admin-dashboard/` | superuser 전용, 봇/사람 구분 |
| Sentry | `SENTRY_DSN` 환경변수 | production only |
| DB 백업 | `python manage.py backup_db` | dumpdata JSON, Cron 가능 |

**context_processors 등록 순서** (두 settings 파일 모두):
```python
'core.context_processors.visitor_counts',
'core.context_processors.toast_messages',
'core.context_processors.site_config',
'core.context_processors.seo_meta',
```

**VisitorLog 모델에 봇 구분 필드 있음:**
- `user_agent`: TextField
- `is_bot`: BooleanField
- `get_visitor_stats(days, exclude_bots=True)` 로 사람만 필터링 가능
