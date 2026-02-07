# Eduitit 서비스 핵심 기능 사용 설명서

> 이 문서는 2026-02-08에 구현된 5개 Phase (Toast, Banner/SEO, Feedback, Dashboard, Sentry/Backup) 기능의 사용법을 안내합니다.

---

## 1단계: Toast 알림 시스템

### 개요
모든 페이지에서 성공/에러/경고/정보 메시지를 우측 상단에 clay 스타일 팝업으로 표시합니다.
Django의 `messages` 프레임워크를 그대로 사용하므로 기존 코드 수정 없이 바로 작동합니다.

### 사용법

#### View에서 메시지 발생시키기
```python
from django.contrib import messages

def my_view(request):
    messages.success(request, '저장되었습니다!')      # 초록색 체크 아이콘
    messages.error(request, '오류가 발생했습니다.')     # 빨간색 X 아이콘
    messages.warning(request, '주의가 필요합니다.')     # 주황색 경고 아이콘
    messages.info(request, '안내 메시지입니다.')        # 파란색 정보 아이콘
    return redirect('home')
```

#### 동작 방식
- 메시지가 발생하면 **우측 상단**에 clay-card 스타일로 3초간 표시 후 자동 사라짐
- 사용자가 **X 버튼**을 눌러 수동으로 닫을 수도 있음
- 여러 메시지가 동시에 쌓이면 위에서 아래로 순서대로 표시

### 관련 파일
- `core/context_processors.py` → `toast_messages()` 함수
- `core/templates/base.html` → Alpine.js toast 컴포넌트

---

## 2단계: 글로벌 배너 관리

### 개요
사이트 상단에 공지사항, 이벤트, 점검 안내 등을 배너로 표시합니다.
관리자 페이지(Admin)에서 텍스트, 색상, 링크를 자유롭게 설정할 수 있습니다.

### 사용법

#### 배너 설정하기
1. 관리자 페이지 접속: `https://eduitit.site/secret-admin-kakio/`
2. **사이트 설정 (SiteConfig)** 클릭
3. 아래 항목 설정 후 저장:

| 항목 | 설명 | 예시 |
|------|------|------|
| 배너 활성화 | 체크하면 배너 표시 | ✅ |
| 배너 텍스트 | 표시할 문구 (최대 200자) | `2월 업데이트: 새로운 AI 도구가 추가되었습니다!` |
| 배너 색상 | HEX 색상 코드 | `#7c3aed` (보라), `#dc2626` (빨강), `#16a34a` (초록) |
| 배너 링크 URL | 클릭 시 이동할 주소 (선택) | `https://eduitit.site/about/` |

#### 배너 끄기
- Admin에서 **배너 활성화** 체크 해제 후 저장

#### 사용자 경험
- 배너는 네비게이션 바 위에 고정 표시
- 사용자가 **X 버튼**을 눌러 개별적으로 닫을 수 있음 (페이지 새로고침 시 다시 표시)

### 관련 파일
- `core/models.py` → `SiteConfig` 모델 (싱글톤)
- `core/context_processors.py` → `site_config()` 함수
- `core/admin.py` → `SiteConfigAdmin`

---

## 3단계: SEO 메타태그 (OpenGraph)

### 개요
SNS 공유 시 썸네일, 제목, 설명이 올바르게 표시되도록 동적 OpenGraph 메타태그를 제공합니다.
기본값이 자동 설정되며, 각 앱의 View에서 개별적으로 override할 수 있습니다.

### 사용법

#### 기본값 (자동 적용)
모든 페이지에 아래 기본값이 자동으로 적용됩니다:
- **og:title**: `Eduitit - 선생님의 스마트한 하루`
- **og:description**: `AI 프롬프트 레시피, 도구 가이드, 교육용 게임까지...`
- **og:image**: `https://eduitit.site/static/images/eduitit_og.png`
- **og:url**: 현재 페이지 URL (자동 생성)

#### 특정 페이지에서 커스텀 메타태그 설정
```python
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'products/detail.html', {
        'product': product,
        # 아래 키를 넘기면 기본값 대신 이 값이 사용됨
        'og_title': f'{product.title} - Eduitit',
        'og_description': product.description[:150],
        'og_image': product.thumbnail.url,
    })
```

#### 적용되는 태그 목록
- `og:title`, `og:description`, `og:image`, `og:url`, `og:type`
- `twitter:card`, `twitter:title`, `twitter:description`, `twitter:image`

### 관련 파일
- `core/context_processors.py` → `seo_meta()` 함수
- `core/templates/base.html` → `<head>` 내 동적 메타태그

---

## 4단계: 피드백 위젯 (의견 보내기)

### 개요
모든 페이지 우측 하단에 **플로팅 피드백 버튼**이 표시됩니다.
로그인하지 않은 사용자(게스트)도 의견을 보낼 수 있으며, Admin에서 확인/관리합니다.

### 사용법

#### 사용자 입장 (의견 보내기)
1. 화면 우측 하단의 **보라색 말풍선 버튼** 클릭
2. 폼이 열리면 아래 항목 작성:

| 항목 | 필수 여부 | 설명 |
|------|-----------|------|
| 이름 | 필수 | 로그인 시 자동 채워짐 |
| 이메일 | 선택 | 로그인 시 자동 채워짐 |
| 카테고리 | 필수 | 버그 신고 / 제안·건의 / 기타 |
| 내용 | 필수 | 최대 1000자 |

3. **보내기** 버튼 클릭 → 성공 메시지 표시 후 자동 닫힘

#### 관리자 입장 (피드백 확인)
1. Admin 접속: `https://eduitit.site/secret-admin-kakio/`
2. **피드백 (Feedback)** 목록에서 확인
3. 기능:
   - **카테고리별 필터링**: 버그 / 제안 / 기타
   - **처리 완료 체크**: 목록에서 바로 체크박스로 토글 가능
   - **검색**: 이름, 이메일, 내용으로 검색

### 엔드포인트
- POST `/feedback/` — HTMX 및 일반 폼 모두 지원

### 관련 파일
- `core/models.py` → `Feedback` 모델
- `core/views.py` → `feedback_view()`
- `core/urls.py` → `/feedback/` 경로
- `core/admin.py` → `FeedbackAdmin`
- `core/templates/base.html` → 플로팅 위젯 UI

---

## 5단계: 관리자 대시보드 (방문자 통계)

### 개요
superuser만 접근 가능한 대시보드에서 방문자 통계를 시각화합니다.
외부 라이브러리(Chart.js 등) 없이 CSS로 구현한 바 차트를 제공합니다.

### 접속 방법
- URL: `https://eduitit.site/admin-dashboard/`
- **조건**: superuser 계정으로 로그인 필수 (일반 사용자는 홈으로 리다이렉트)

### 대시보드 구성

| 섹션 | 내용 |
|------|------|
| 요약 카드 (4개) | 오늘 방문자 / 이번 주 / 이번 달 / 전체 누적 |
| 일별 차트 | 최근 30일 방문자 수 바 차트 |
| 주간 테이블 | 최근 8주 방문자 수 + 가로 바 차트 |

### 관련 파일
- `core/utils.py` → `get_visitor_stats()`, `get_weekly_stats()`
- `core/views.py` → `admin_dashboard_view()`
- `core/templates/core/admin_dashboard.html`
- `core/urls.py` → `/admin-dashboard/`

---

## 6단계: Sentry 에러 모니터링

### 개요
프로덕션 환경에서 발생하는 에러를 Sentry에 자동으로 리포트합니다.
`DEBUG=False`일 때만 활성화되므로 로컬 개발에는 영향 없습니다.

### 설정 방법

#### Railway/Render 환경변수 추가
```
SENTRY_DSN=https://examplePublicKey@o0.ingest.sentry.io/0
```

#### Sentry 프로젝트 생성 (최초 1회)
1. [sentry.io](https://sentry.io) 접속 → 회원가입/로그인
2. **Create Project** → Python > Django 선택
3. 생성된 **DSN** 값을 복사
4. Railway/Render 환경변수에 `SENTRY_DSN` 으로 등록
5. 재배포하면 자동 활성화

#### 설정값
| 항목 | 값 | 설명 |
|------|----|------|
| traces_sample_rate | 0.2 | 전체 요청의 20%만 성능 추적 (비용 절감) |
| profiles_sample_rate | 0.1 | 전체 요청의 10%만 프로파일링 |

#### 동작 확인
- Sentry 대시보드에서 에러 발생 시 실시간 알림 확인
- 환경변수 `SENTRY_DSN`이 비어있거나 `DEBUG=True`이면 비활성 상태

### 관련 파일
- `config/settings.py` → Sentry 초기화 코드
- `config/settings_production.py` → 동일하게 동기화
- `requirements.txt` → `sentry-sdk>=2.0.0`

---

## 7단계: 데이터베이스 자동 백업

### 개요
`django-dbbackup`을 사용하여 데이터베이스를 파일로 백업합니다.
수동 실행 또는 cron/Railway Scheduled Task로 자동화할 수 있습니다.

### 사용법

#### 수동 백업 실행
```bash
# 기본 백업 (이전 백업 자동 정리)
python manage.py backup_db

# django-dbbackup 직접 사용
python manage.py dbbackup          # 백업 생성
python manage.py dbrestore         # 백업 복원
python manage.py dbbackup --clean  # 백업 후 오래된 파일 정리
```

#### 백업 파일 위치
```
eduitit/
└── backups/
    ├── default-2026-02-08-1200.dump    # PostgreSQL 덤프
    └── default-2026-02-07-1200.dump
```

#### 자동 백업 설정 (Railway Cron Job)
Railway에서 Scheduled Task를 추가합니다:
```
# 매일 새벽 3시 (KST) 자동 백업
python manage.py backup_db
```

설정 경로: Railway Dashboard → 프로젝트 → **Cron Jobs** → Add Job

#### 백업 복원 (긴급 시)
```bash
# 가장 최근 백업으로 복원
python manage.py dbrestore

# 특정 백업 파일로 복원
python manage.py dbrestore --input-filename backups/default-2026-02-08-1200.dump
```

### 관련 파일
- `core/management/commands/backup_db.py` → 백업 커맨드
- `config/settings.py` → `DBBACKUP_STORAGE` 설정
- `config/settings_production.py` → 동일하게 동기화
- `requirements.txt` → `django-dbbackup>=4.1.0`

---

## 부록: 설정 동기화 체크리스트

아래 항목이 `settings.py`와 `settings_production.py` 양쪽에 모두 존재하는지 확인하세요:

```
INSTALLED_APPS:
  ✅ 'dbbackup'

TEMPLATES > context_processors:
  ✅ 'core.context_processors.visitor_counts'
  ✅ 'core.context_processors.toast_messages'
  ✅ 'core.context_processors.site_config'
  ✅ 'core.context_processors.seo_meta'

하단 설정:
  ✅ SENTRY_DSN + sentry_sdk.init()
  ✅ DBBACKUP_STORAGE + DBBACKUP_STORAGE_OPTIONS
```

## 부록: 전체 URL 맵

| URL | 기능 | 접근 권한 |
|-----|------|-----------|
| `/feedback/` | 피드백 제출 (POST) | 모든 사용자 |
| `/admin-dashboard/` | 방문자 통계 대시보드 | superuser만 |
| `/secret-admin-kakio/` | Django Admin (SiteConfig, Feedback 관리) | staff/superuser |
