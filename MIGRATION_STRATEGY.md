# Eduitit: Django → Next.js 마이그레이션 전략

> 작성일: 2026-02-11
> 작성: Claude Code 분석 기반

---

## 솔직한 진단

### 현재 상태
- Django 6 모놀리스, 14개 앱, 40+ 모델, 수천 줄의 비즈니스 로직
- Django 템플릿 + Alpine.js + HTMX 프론트엔드
- Railway + Neon PostgreSQL + Cloudinary
- AI(Gemini), RAG(ChromaDB), OAuth(카카오/네이버), 사주 계산 등 복잡한 백엔드 로직

### 한 번에 전체 마이그레이션? → 비추천

**이유:**
1. **규모**: 14개 앱 × (모델 + 뷰 + 템플릿 + 비즈니스 로직) = 최소 3-6개월 풀타임 작업
2. **위험**: 서비스 중단 없이 전환해야 하고, 기존 사용자 데이터도 유지해야 함
3. **Django의 장점을 버림**: Admin 패널, ORM, allauth, management commands - 이것들을 Next.js에서 재구현하려면 엄청난 노력 필요
4. **백엔드는 여전히 필요**: 사주 계산, ChromaDB RAG, 문서 처리(HWP/PDF/PPTX) 등은 Python이 훨씬 유리 - Next.js API Routes만으로는 부족

### 추천 전략: 점진적 하이브리드 마이그레이션

**Phase 1 → Phase 2 → Phase 3** 순서로, 서비스를 중단하지 않고 점진적으로 전환

---

## Phase 1: Django를 API 백엔드로 전환 (2-3주)

**목표**: Django를 REST API 서버로 만들어 Next.js 프론트엔드와 분리할 기반 마련

### 1.1 Django REST Framework 추가
```bash
pip install djangorestframework djangorestframework-simplejwt django-cors-headers
```

### 1.2 핵심 API 엔드포인트 구축

| 앱 | 엔드포인트 | 우선순위 |
|---|---|---|
| core | `/api/auth/`, `/api/users/me/`, `/api/posts/` | 필수 |
| products | `/api/products/`, `/api/products/{id}/` | 필수 |
| fortune | `/api/fortune/analyze/`, `/api/fortune/daily/`, `/api/fortune/history/` | 높음 |
| ssambti | `/api/ssambti/start/`, `/api/ssambti/result/` | 높음 |
| studentmbti | `/api/sessions/`, `/api/sessions/{code}/join/`, `/api/sessions/{id}/results/` | 높음 |
| collect | `/api/collections/`, `/api/collections/{code}/submit/` | 중간 |
| 기타 | 나머지 앱들 | 낮음 |

### 1.3 인증 체계
- Django REST Framework + SimpleJWT
- 기존 allauth(카카오/네이버 OAuth)는 Django 측에서 유지
- Next.js는 JWT 토큰으로 API 호출

### 수정 파일
- `requirements.txt` - DRF, JWT, CORS 추가
- `config/settings.py` / `settings_production.py` - DRF, CORS 설정
- 각 앱에 `serializers.py`, `api_views.py` 추가
- `config/urls.py` - `/api/` prefix 라우팅

---

## Phase 2: Next.js 프론트엔드 신규 구축 (4-6주)

**목표**: Next.js App Router + TypeScript로 새로운 프론트엔드 구축

### 2.1 프로젝트 구조
```
eduitit-web/                    # 새로운 Next.js 프로젝트
├── app/
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   └── signup/page.tsx
│   ├── (main)/
│   │   ├── page.tsx            # 홈 (서비스 카드 그리드)
│   │   ├── fortune/
│   │   │   ├── page.tsx        # 사주 입력
│   │   │   ├── result/page.tsx # 결과
│   │   │   └── history/page.tsx
│   │   ├── ssambti/page.tsx
│   │   ├── student-mbti/
│   │   │   ├── page.tsx        # 세션 관리
│   │   │   └── [code]/page.tsx # 학생 참여
│   │   ├── collect/
│   │   └── ...
│   ├── api/                    # Next.js API Routes (프록시 or 경량 로직)
│   └── layout.tsx
├── components/
│   ├── ui/                     # 공통 UI (Button, Card, Modal...)
│   ├── clay/                   # Claymorphism 디자인 시스템
│   ├── sns/                    # SNS 피드 위젯
│   └── ...
├── lib/
│   ├── api.ts                  # Django API 클라이언트
│   ├── auth.ts                 # JWT 인증
│   └── types.ts                # TypeScript 타입 정의
└── ...
```

### 2.2 기술 스택

| 영역 | 기술 |
|---|---|
| Framework | Next.js 15 (App Router) |
| Language | TypeScript |
| Styling | Tailwind CSS v4 (기존 디자인 시스템 유지) |
| State | Zustand or Jotai (경량) |
| Forms | React Hook Form + Zod |
| Data Fetching | TanStack Query (서버 상태 관리) |
| Auth | NextAuth.js (카카오/네이버 OAuth) |
| Markdown | react-markdown |
| Charts | Recharts |
| Streaming | Vercel AI SDK (AI 스트리밍 응답) |

### 2.3 마이그레이션 순서 (앱별)
1. **홈 + 인증** (로그인, 회원가입, 프로필) - 기반
2. **products** (서비스 카드 목록) - 단순
3. **ssambti** (쌤BTI) - 퀴즈 UI, 결과 표시
4. **studentmbti** (학생 MBTI) - 실시간 업데이트가 있어 Next.js 장점 발휘
5. **collect** (간편 수합) - 파일 업로드, 대시보드
6. **fortune** (사주) - 가장 복잡, AI 스트리밍
7. **나머지 앱들** - 하나씩

---

## Phase 3: 인프라 전환 (Phase 2와 병행)

**목표**: Vercel + 별도 백엔드로 분리 배포

### 3.1 최종 아키텍처
```
┌─────────────────┐     ┌──────────────────┐
│   Vercel         │     │   Railway/Render  │
│   (프론트엔드)    │────▶│   (Django API)    │
│   Next.js        │     │   DRF + Gunicorn  │
│   Edge Functions │     │                   │
└─────────────────┘     └──────┬───────────┘
                               │
                    ┌──────────┼──────────┐
                    │          │          │
              ┌─────┴───┐ ┌───┴────┐ ┌───┴────────┐
              │  Neon    │ │Cloudinary│ │  ChromaDB  │
              │PostgreSQL│ │ (미디어) │ │  (RAG)     │
              └─────────┘ └────────┘ └────────────┘
```

### 3.2 배포 구성

| 서비스 | 플랫폼 | 역할 |
|---|---|---|
| Next.js 프론트엔드 | **Vercel** | SSR, 정적 페이지, Edge Functions |
| Django API | **Railway** (유지) | REST API, AI 처리, RAG, 문서 처리 |
| PostgreSQL | **Neon** (유지) | 데이터베이스 |
| 미디어 | **Cloudinary** (유지) | 이미지/파일 저장 |
| 도메인 | Vercel에 연결 | 메인 도메인 → Vercel, api.도메인 → Railway |

### 3.3 장점
- **Vercel**: 자동 Preview 배포, Edge CDN, 이미지 최적화, Analytics
- **Railway 유지**: Python 의존 로직(사주 계산, HWP 파싱, ChromaDB) 계속 활용
- **분리 배포**: 프론트만 수정 시 백엔드 재배포 불필요 (빠른 배포)

---

## 현실적 고려사항

### 난이도 평가: ★★★★☆ (어렵지만 충분히 가능)

**어려운 부분:**
- OAuth 흐름 재구현 (NextAuth.js + Django JWT 연동)
- AI 스트리밍 응답 연동 (Vercel AI SDK ↔ Django SSE)
- 14개 앱의 UI를 React 컴포넌트로 재작성
- 기존 HTMX 인터랙션을 React 상태 관리로 전환

**쉬운 부분:**
- Tailwind CSS 디자인 시스템은 그대로 재사용
- Django 모델/비즈니스 로직은 그대로 유지 (API만 추가)
- Neon/Cloudinary 인프라 변경 없음

### 비용 변화

| 항목 | 현재 | 전환 후 |
|---|---|---|
| Railway | ~$5-20/월 | ~$5-20/월 (API만) |
| Vercel | 없음 | 무료~$20/월 (Hobby/Pro) |
| Neon | 현재 요금 | 동일 |
| Cloudinary | 현재 요금 | 동일 |

---

## 대안: Django 내에서 개선 (최소 노력)

만약 전체 마이그레이션이 부담된다면, Django를 유지하면서도 많이 개선할 수 있습니다:

1. **Inertia.js + React**: Django 템플릿 대신 React 컴포넌트 사용, 별도 API 불필요
2. **django-vite + React Islands**: 특정 페이지만 React로 전환
3. **코드 구조 개선**: Service Layer 패턴 도입, 앱 간 의존성 정리
4. **TypeScript 부분 도입**: 프론트엔드 JS를 TS로 전환

---

## 추천 순서 요약

| 단계 | 기간 | 내용 | 서비스 영향 |
|---|---|---|---|
| Phase 1 | 2-3주 | Django API 엔드포인트 추가 (DRF) | 없음 (기존 서비스 유지) |
| Phase 2-1 | 1-2주 | Next.js 프로젝트 셋업 + 홈/인증 | 없음 (병렬 개발) |
| Phase 2-2 | 3-4주 | 앱별 페이지 마이그레이션 | 없음 (병렬 개발) |
| Phase 3 | 1주 | Vercel 배포 + 도메인 전환 | 짧은 전환 시간 |
| 정리 | 1-2주 | Django 템플릿 제거, 테스트, 안정화 | 없음 |

**총 예상: 8-12주** (파트타임 기준 더 길어질 수 있음)
