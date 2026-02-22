# Eduitit 서비스 유기적 연결 전략

## Context

현재 28개 이상의 서비스가 각자 독립된 사일로로 운영되고 있음. 서비스들 사이에 공유 데이터도, 흐름도 없음. 특히 학생 명부가 happy_seed, dutyticker, studentmbti, ppobgi에 중복 관리됨. 교사 입장에서 "시장판에 널부러진 구조"를 넘어 엔터프라이즈급으로 확장하려면 서비스 간 유기적 연결이 필수.

---

## 핵심 진단: 왜 "시장판" 느낌인가

| 문제 | 현황 | 영향 |
|------|------|------|
| **학생 명부 4중 사일로** | HSStudent, DTStudent, studentmbti(문자열), ppobgi(없음) | 학생 이름을 서비스마다 다시 입력해야 함 |
| **결과물이 연결 안 됨** | noticegen→qrgen, studentmbti→fortune 등 경로 없음 | 서비스 완료 후 다음 행동 단절 |
| **"오늘" 개념 부재** | 예약·수합·동의 현황을 한눈에 볼 곳 없음 | 교사가 직접 각 서비스 들어가서 확인 |
| **학생 포털 분산** | 퀴즈 코드, 수합 코드, MBTI 코드 각각 배포 | 학생이 여러 URL/코드를 외워야 함 |

---

## 전략 핵심: 3개 레이어로 연결

```
[레이어 1] 공유 데이터 기반   → roster 앱 (학급·학생 중앙 엔티티)
[레이어 2] 교사 지휘 허브     → Today 지휘소 (오늘의 예약·수합·동의 한눈에)
[레이어 3] 서비스 흐름 연결   → 크로스 추천 배너 + 통합 학생 포털
```

---

## 추천 구현 순서 (Phase별)

### Phase 0 — 빠른 연결 (4일, 리스크 낮음)

**목표**: 기존 서비스를 부수지 않고 연결 시작

1. `studentmbti.TestSession`에 `classroom = FK(HSClassroom, null=True)` 추가
   - 파일: `studentmbti/models.py`
   - 기존 access_code 방식 유지, classroom 선택은 옵션

2. `ppobgi` 뷰에 학급 선택 시 학생 목록 자동 로드 API 추가
   - 파일: `ppobgi/views.py`
   - `GET /ppobgi/api/classroom/<uuid>/students/` → JSON

3. `dutyticker` 학생(DTStudent)을 HSClassroom 기반으로 마이그레이션
   - 파일: `products/models.py`

### Phase 1 — Today 지휘소 (5일, 리스크 낮음)

**목표**: 교사가 매일 아침 열면 "오늘의 할 일"이 보이는 홈

- `home_authenticated_v2.html` 상단에 Today 위젯 삽입
  - 파일: `core/templates/core/home_authenticated_v2.html`
  - 오늘 예약된 특별실 / 진행 중 수합 건수 / 미서명 동의서 수 표시

- `core/views.py`에 `_build_today_context()` 함수 추가
  - 파일: `core/views.py`
  - reservations, collect, consent 3개 앱 데이터를 HTMX로 비동기 로드

- 홈 상단 "오늘 수업 학급" 선택 드롭다운 추가
  - 선택값을 세션에 저장 → 각 서비스에서 기본값으로 사용

### Phase 2 — 크로스 추천 배너 (5일, 리스크 낮음)

**목표**: 서비스 완료 후 자연스럽게 다음 서비스로 안내

```
noticegen 공지문 완성 → "QR코드로 만들기" + "학부모 동의서 받기"
collect 수합 종료 → "다음 수합 만들기"
studentmbti 결과 → "나의 동물 유형은?" (ssambti)
ssambti 결과 → "더 깊은 나를 알고 싶다면" (fortune)
happy_seed 꽃피움 → "오늘의 퀴즈 출제하기" (seed_quiz)
seed_quiz 종료 → "우수 학생에게 씨앗 주기" (happy_seed)
reservations 예약 → "이번 수업에 미술 타임워치" (artclass)
artclass 수업 → "발표자 번호 뽑기" (ppobgi)
```

- `core/suggestions.py` 정적 매핑 딕셔너리 (신규 파일)
- `core/templates/core/partials/service_suggestion.html` 배너 컴포넌트
- 7개 뷰의 결과 페이지에 `{% include %}` 삽입

### Phase 3 — roster 앱 (10일, 리스크 높음, 별도 스프린트)

**목표**: 학생 명부를 플랫폼 공유 엔티티로 승격

- 신규 앱 `roster` 생성
  - `roster.Classroom` (school_year, grade, class_no, teacher FK)
  - `roster.Student` (classroom FK, name, number)

- `happy_seed.HSClassroom` → `roster.Classroom` 1:1 참조로 재구성
  - HSClassroom의 roster 전용 필드를 Classroom으로 이전
  - HSClassroom에는 게임화 전용 필드만 남김 (slug, garden 설정 등)

- 각 앱이 `roster`를 참조하도록 순차 마이그레이션
  - `seed_quiz`: `from happy_seed.models import HSClassroom` → `from roster.models import Classroom`
  - `studentmbti`: Phase 0의 HSClassroom FK → Classroom FK로 업그레이드
  - `dutyticker`: DTStudent → roster.Student 연결

- **주의**: 프로덕션 DB 백업 후 진행, `python manage.py check` 필수

### Phase 4 — 행정 서비스 학급 연결 (3일)

- `collect.CollectionRequest`에 `classroom = FK(roster.Classroom, null=True)` 추가
  - 수합 생성 시 "학급에서 학생 명단 가져오기" 버튼
- `consent.SignatureRequest`에 `classroom` FK 추가
  - 동의서 발송 수신자를 학급 학생 목록에서 자동 채우기

### Phase 5 — 통합 학생 포털 (7일)

**목표**: 학생에게 하나의 URL로 모든 활동 접근

```
/s/<classroom_slug>/          ← 학급 포털 홈
/s/<classroom_slug>/quiz/     ← 오늘의 seed_quiz
/s/<classroom_slug>/bloom/    ← happy_seed 정원 보기
/s/<classroom_slug>/mbti/     ← studentmbti 참여
```

- 교사가 "학생 포털 QR 생성" 버튼 클릭 → qrgen에 URL 자동 전달 → QR 이미지 다운로드
- 학생: 칠판 QR 스캔 → 포털 진입 → 오늘 활성화된 활동 자동 노출

---

## 핵심 파일 목록

| Phase | 파일 | 변경 내용 |
|-------|------|-----------|
| 0 | `studentmbti/models.py` | TestSession에 classroom FK 추가 |
| 0 | `ppobgi/views.py` | 학급 학생 목록 API 추가 |
| 0 | `products/models.py` | DTStudent 마이그레이션 |
| 1 | `core/views.py` | `_build_today_context()` 추가 |
| 1 | `core/templates/core/home_authenticated_v2.html` | Today 위젯 삽입 |
| 2 | `core/suggestions.py` (신규) | 크로스 추천 정적 매핑 |
| 2 | `core/templates/core/partials/service_suggestion.html` (신규) | 배너 컴포넌트 |
| 3 | `roster/` (신규 앱) | Classroom, Student 모델 |
| 3 | `happy_seed/models.py` | HSClassroom → roster.Classroom 1:1 참조 |
| 4 | `collect/models.py` | classroom FK 추가 |
| 4 | `consent/models.py` | classroom FK 추가 |
| 5 | `roster/views.py` | student_portal 뷰 |

---

## 검증 방법

- **Phase 0**: `python manage.py check` → studentmbti TestSession에서 HSClassroom 선택 후 세션 생성 → ppobgi에서 학급 선택 후 학생 자동 로드 확인
- **Phase 1**: 로그인 후 홈에서 오늘의 예약/수합/동의 위젯 표시 확인
- **Phase 2**: noticegen 완료 화면에서 qrgen 추천 배너 노출 확인
- **Phase 3**: `python manage.py migrate` 성공 + 기존 happy_seed, seed_quiz 정상 동작 확인
- **Phase 5**: `/s/<classroom_slug>/` 접속 시 학생이 퀴즈/MBTI/정원 진입 가능 확인

---

## 진행 상태

- [ ] Phase 0 — 빠른 연결
- [ ] Phase 1 — Today 지휘소
- [ ] Phase 2 — 크로스 추천 배너
- [ ] Phase 3 — roster 앱 (별도 스프린트)
- [ ] Phase 4 — 행정 서비스 학급 연결
- [ ] Phase 5 — 통합 학생 포털
