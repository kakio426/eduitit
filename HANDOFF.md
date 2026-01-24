# 작업 인계 문서

> 생성일: 2025-01-24
> 세션: Padlet Bot 앱 생성 + 소셜 로그인 오류 수정

---

## 완료된 작업

### 1. padlet_bot 앱 생성 (Django 6.0)
- [x] 앱 디렉토리 및 기본 파일 생성
- [x] `models.py` - PadletDocument, LinkedPadletBoard, PadletBotSettings 모델
- [x] `rag_utils.py` - CSV 파싱 추가, school_violence 공통 함수 재사용
- [x] `forms.py` - 문서 업로드 폼
- [x] `views.py` - 채팅, 문서 관리, API 연동 뷰
- [x] `urls.py` - URL 패턴 등록
- [x] `admin.py` - Admin 등록
- [x] 템플릿: `chat.html`, `manage_docs.html`, `api_connect.html`
- [x] `padlet_api.py` - 패들릿 API 클라이언트
- [x] 마이그레이션 생성 및 적용 완료

### 2. 네이버/카카오 소셜 로그인 오류 수정
- [x] **Site 도메인 수정**: `example.com` → `web-production-f2869.up.railway.app`
- [x] **settings.py 환경변수명 수정**:
  - `NAVER_SECRET` → `NAVER_CLIENT_SECRET`
  - `KAKAO_SECRET` → `KAKAO_CLIENT_SECRET`

---

## 진행 중인 작업: 소셜 로그인 완료 필요

### 남은 작업 1: KAKAO_CLIENT_SECRET 추가

`.env` 파일에 `KAKAO_CLIENT_SECRET`이 **없음**. 추가 필요:

```env
# .env에 추가
KAKAO_CLIENT_SECRET=카카오_시크릿_키
```

카카오 개발자 콘솔 → 내 애플리케이션 → 보안 → Client Secret에서 확인

### 남은 작업 2: Callback URL 확인

네이버/카카오 개발자 콘솔에 아래 URL이 등록되어 있어야 함:

| 서비스 | Callback URL |
|--------|--------------|
| 카카오 | `https://web-production-f2869.up.railway.app/accounts/kakao/login/callback/` |
| 네이버 | `https://web-production-f2869.up.railway.app/accounts/naver/login/callback/` |

**주의**: django-allauth 형식은 `/accounts/{provider}/login/callback/`

---

## padlet_bot 앱 구조

```
padlet_bot/
├── models.py             # PadletDocument, LinkedPadletBoard, PadletBotSettings
├── padlet_api.py         # 패들릿 API 클라이언트
├── rag_utils.py          # CSV 파싱 + ChromaDB RAG
├── views.py              # 채팅, 문서 관리, API 연동 뷰
├── urls.py, forms.py, admin.py, apps.py
├── migrations/
│   ├── 0001_initial.py
│   └── 0002_linkedpadletboard.py
└── templates/padlet_bot/
    ├── chat.html         # 채팅 UI
    ├── manage_docs.html  # 파일 업로드 관리
    └── api_connect.html  # API 연동 페이지
```

### URL 구조
- `/padlet/` - 채팅 메인
- `/padlet/docs/` - 파일 업로드 관리 (관리자)
- `/padlet/api/` - API 연동 페이지 (관리자)

---

## 주요 수정 파일

### 소셜 로그인 관련
- `config/settings.py:146-163` - SOCIALACCOUNT_PROVIDERS 환경변수명 수정
- `db.sqlite3` - django_site 테이블 도메인 수정됨

### padlet_bot 관련
- `config/settings.py:54` - INSTALLED_APPS에 앱 등록
- `config/urls.py:35` - URL 패턴 추가
- `.env.example` - PADLET_API_KEY 추가

---

## 환경변수 체크리스트

```env
# 소셜 로그인 (필수)
KAKAO_CLIENT_ID=08173c0ab91102b7cbf348564b4cd0ea  ✅ 있음
KAKAO_CLIENT_SECRET=???                           ❌ 없음 - 추가 필요!
NAVER_CLIENT_ID=FK4ZWrVuv1I80fjRhrQb              ✅ 있음
NAVER_CLIENT_SECRET=prX2VqR53R                    ✅ 있음

# 패들릿 (선택)
PADLET_API_KEY=???                                 (Pro 계정 시 추가)
```

---

## 다음에 해야 할 작업

1. **KAKAO_CLIENT_SECRET 추가** → `.env` 파일에 추가
2. **Callback URL 확인** → 네이버/카카오 개발자 콘솔
3. **Railway 재배포** → 환경변수 반영
4. **소셜 로그인 테스트**
5. **padlet_bot 테스트** → `/padlet/` 접속

---

## 마지막 상태

- **배포 도메인**: `https://web-production-f2869.up.railway.app/`
- **Site 도메인**: `web-production-f2869.up.railway.app` (수정됨)
- **마이그레이션**: 완료
- **소셜 로그인**: KAKAO_CLIENT_SECRET 추가 후 동작 예상

---

## 이전 세션 작업

- 2025-01-23: DutyTicker 디자인 통합, AutoArticle 오류 수정, 헬스체크 테스트

---

## 다음 세션 시작 방법

```
HANDOFF.md 읽고 이어서 작업해줘
```
