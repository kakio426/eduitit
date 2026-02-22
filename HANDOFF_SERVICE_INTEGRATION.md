# 서비스 연결 전략 구현 핸드오프

작성일: 2026-02-22
기준 브랜치: (현재 작업 트리, 미커밋 상태)

---

## 완료된 작업

### Phase 0 — 네비게이션 학급 선택기 ✅

**목적**: 전역 navbar에 "현재 학급" 단축키 드롭다운 추가. DTStudent 없는 신규 교사에겐 미표시.

| 파일 | 변경 내용 |
|------|-----------|
| `core/context_processors.py` | `active_classroom()` 함수 추가 |
| `config/settings.py` | `context_processors`에 `core.context_processors.active_classroom` 등록 |
| `config/settings_production.py` | 동일 |
| `core/urls.py` | `POST /api/set-classroom/` 라우트 추가 (`set_active_classroom` 이름) |
| `core/views.py` | `set_active_classroom()` 뷰 추가 (파일 맨 끝) |
| `core/templates/base.html` | 데스크탑 nav에 학급 드롭다운 칩, 모바일 메뉴에 학급 단축키 섹션, `classroomPicker()` Alpine 컴포넌트 스크립트 |

**세션 키**:
- `request.session['active_classroom_source']` = `'hs'`
- `request.session['active_classroom_id']` = HSClassroom UUID 문자열

**컨텍스트 변수** (모든 템플릿에서 사용 가능):
- `active_classroom` — `HSClassroom` 인스턴스 또는 `None`
- `has_hs_classrooms` — `bool` (칩 표시 여부 제어)
- `hs_classrooms_json` — Alpine에서 드롭다운 채우는 JSON 문자열

**동작 조건**:
- `has_hs_classrooms = False`이면 navbar에 칩 자체가 렌더링되지 않음
- 학급 삭제 또는 비활성화 시 context processor가 세션을 자동 초기화

---

### Phase 1 Part A — ppobgi 신규 API + 자동 채우기 ✅

| 파일 | 변경 내용 |
|------|-----------|
| `ppobgi/views.py` | `classroom_students(request, pk)` 뷰 추가 |
| `ppobgi/urls.py` | `GET /ppobgi/api/classroom/<uuid:pk>/students/` 라우트 추가 |
| `ppobgi/templates/ppobgi/main.html` | `data-classroom-url`, `data-classroom-name` 속성 + 자동 로드 인라인 JS |

**기존 API 유지**: `GET /ppobgi/api/roster-names/` (DTStudent 기반) — 변경 없음.

**자동 채우기 동작**:
- `active_classroom`이 세션에 있으면 페이지 로드 시 자동으로 textarea에 학생 명단 채움
- 별빛 추첨기(stars)와 사다리 뽑기(ladder) textarea 모두 채움
- 성공 메시지: `"현재 학급 [3학년 2반] 명단 28명이 자동으로 불러와졌습니다."`
- 학급 없으면 기존 방식 그대로 (변경 없음)

---

### Phase 1 Part B — studentmbti classroom FK 추가 ✅ (모델+마이그레이션만)

| 파일 | 변경 내용 |
|------|-----------|
| `studentmbti/models.py` | `TestSession.classroom` FK 추가 (`HSClassroom`, `null=True`, `on_delete=SET_NULL`) |
| `studentmbti/migrations/0007_add_classroom_to_testsession.py` | 마이그레이션 생성 완료 |

**마이그레이션 적용 필요**: `python manage.py migrate studentmbti`

---

## 미완료 작업

### Phase 1 Part B 나머지 — studentmbti 뷰 자동 연결

`studentmbti/views.py`에서 세션 생성 시 세션 학급 자동 연결 로직이 아직 추가되지 않음.

```python
# studentmbti/views.py — 세션 생성 뷰에서 아래 패턴 추가
# (create 뷰 찾아서 session 저장 직전에)
source = request.session.get('active_classroom_source')
cid = request.session.get('active_classroom_id')
if source == 'hs' and cid:
    try:
        from happy_seed.models import HSClassroom
        classroom = HSClassroom.objects.get(pk=cid, teacher=request.user)
        test_session.classroom = classroom
    except Exception:
        pass
```

studentmbti 결과 화면에서 학급 정보 표시 여부는 선택적 개선사항.

---

### Phase 2 — 크로스 추천 배너

신규 파일 2개 생성 필요:
- `core/suggestions.py` — 정적 추천 매핑 딕셔너리
- `core/templates/core/partials/service_suggestion.html` — 배너 컴포넌트

각 서비스 결과 페이지에 `{% include %}` 삽입 대상:
- `noticegen` → qrgen, consent 추천
- `collect` → collect ("다음 수합 만들기")
- `studentmbti` → ssambti 추천
- `ssambti` → fortune 추천
- `happy_seed` → seed_quiz 추천
- `seed_quiz` → happy_seed 추천
- `reservations` → artclass 추천
- `artclass` → ppobgi 추천

```python
# core/suggestions.py 참고 구조
SUGGESTIONS = {
    'noticegen': ['qrgen', 'consent'],
    'collect': ['collect'],
    'studentmbti': ['ssambti'],
    'ssambti': ['fortune'],
    'happy_seed': ['seed_quiz'],
    'seed_quiz': ['happy_seed'],
    'reservations': ['artclass'],
    'artclass': ['ppobgi'],
}
```

배너 컴포넌트 설계 원칙:
- 팝업/모달 없음, 결과 페이지 하단 1~2개
- Product 모델에서 `title` 매칭으로 URL/아이콘 조회
- `{% include 'core/partials/service_suggestion.html' with service_key='noticegen' %}`

---

### Phase 3 — Today 위젯 (선택적)

`core/views.py` `_build_today_context()` HTMX 비동기 함수 추가.
`core/templates/core/home_authenticated_v2.html` 조건부 위젯 삽입.
**데이터 없으면 렌더링 안 함** 원칙 준수.

---

## 검증 체크리스트

### Phase 0 검증
- [ ] HSClassroom 없는 교사 로그인 → navbar에 학급 칩 미표시
- [ ] HSClassroom 있는 교사 → 칩 표시, 드롭다운으로 선택 가능
- [ ] 학급 선택 후 페이지 이동 → 칩에 학급명 유지
- [ ] "선택 해제" 클릭 → 칩 비어있음
- [ ] 모바일 메뉴에서도 학급 목록 표시/선택 가능

### Phase 1 ppobgi 검증
- [ ] 세션 학급 설정 후 `/ppobgi/` 진입 → textarea 자동 채워짐
- [ ] 세션 학급 없을 때 → textarea에 기본 예시 이름 (기존 동작 그대로)
- [ ] 기존 "당번 명단 불러오기" 버튼 → 기존대로 DTStudent 불러옴
- [ ] `GET /ppobgi/api/classroom/<uuid>/students/` → 타인 학급으로 404 반환 확인

### Phase 1 studentmbti 검증
- [ ] `python manage.py migrate` 오류 없음
- [ ] 학급 삭제 → TestSession 삭제 안 되고 classroom=NULL로 변경

---

## 주의사항

- **`ppobgi/views.py`에 `import uuid as uuid_module`이 추가됐지만 현재 사용하지 않음** — 다음 세션에서 정리 가능
- `active_classroom` context processor는 인증된 사용자마다 HSClassroom 쿼리 1회 발생. 트래픽이 많아지면 `request._cache`로 결과 캐싱 고려
- `ppobgi/main.html`의 자동 로드 스크립트는 Alpine.js 없이 순수 JS로 작성됨 — ppobgi 앱이 `hide_navbar: True`를 사용해 Alpine이 늦게 로드될 수 있는 상황에 안전
