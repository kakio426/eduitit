# Phase 4 설계서: 통합 학급/학생 명단(roster) 아키텍처

작성일: 2026-02-22  
상태: 설계 완료 (개발 착수 전)

---

## 1) 목표

교사가 여러 서비스에서 같은 학급/학생 정보를 반복 입력하지 않도록, 공통 명단 기반을 만든다.

- 서비스별 입력 중복 제거
- 학급 단축키와 자동 채움 정확도 향상
- 학년도 교체 시 안전한 이관/보관 절차 제공

---

## 2) 착수 조건 (필수)

아래 4개 조건을 만족할 때만 착수한다.

1. 학년도 전환 시점(명단 변경이 많은 시기) 전후로 운영 공지가 준비됨
2. 데이터 보존 정책(보관 기간, 삭제 기준) 확정
3. 학교별 내부 안내 문안(학운위 설명 포함) 확정
4. 기존 서비스(happy_seed, ppobgi, studentmbti)와 충돌 없는 백업/롤백 계획 확정

주의: 현재 스프린트에서는 구현하지 않는다. 설계와 검증 계획만 유지한다.

---

## 3) 범위 / 비범위

### 범위

- `roster` 앱 신규 도입
- 학급/학생 기본 정보의 단일 기준 저장소 구성
- 기존 서비스에서 명단을 읽는 어댑터 계층 제공
- 학년도 이관(복제/비활성화) 기능

### 비범위

- 학생/학부모 신규 대규모 온보딩 UI
- 고급 통계/리포트 분석 기능
- 외부 SIS(나이스 등) 자동 연동

---

## 4) 핵심 원칙

1. 강제 전환 금지: 기존 서비스는 기존 방식으로도 계속 동작
2. 읽기 우선 전환: 먼저 조회를 공통화, 쓰기 전환은 이후 단계
3. 교사 용어 사용: "학급 단축키", "현재 학급", "명단 가져오기"
4. 개인정보 최소화: 꼭 필요한 필드만 저장

---

## 5) 데이터 모델 제안 (초안)

## `RosterSchool`
- `id`, `owner(user)`, `name`, `year`, `is_active`, timestamps

## `RosterClassroom`
- `id(UUID)`, `school(FK)`, `name`, `grade`, `class_no`, `slug`, `is_active`, timestamps

## `RosterStudent`
- `id(UUID)`, `classroom(FK)`, `name`, `number`, `is_active`, `archived_at`, timestamps

## `RosterAlias` (선택)
- 기존 서비스 레코드와 매핑(`source`, `source_id`, `roster_student_id`)
- 단계적 전환 동안 호환성 보장

권장 인덱스:
- `(school_id, is_active)`
- `(classroom_id, number, is_active)`
- `(classroom_id, name, is_active)`

---

## 6) 기존 서비스 연계 방식

## happy_seed
- `HSClassroom/HSStudent`를 즉시 제거하지 않음
- 읽기 경로에 roster 우선 조회 옵션을 추가
- 신규 생성은 기능 플래그로 단계적 전환

## ppobgi
- 현재 `HSClassroom` API 유지
- roster 준비 후 `/ppobgi/api/classroom/<uuid>/students/` 내부 조회만 교체

## studentmbti
- `TestSession.classroom`은 유지
- 세션 생성 시 roster classroom으로 매핑 가능하도록 어댑터 추가

## duty 관련 서비스
- `DTStudent`는 1차에서 유지
- 2차에서 roster 동기화 배치 작업 제공

---

## 7) 학년도 전환 시나리오

1. 교사가 "학년도 시작 준비" 버튼 클릭
2. 현재 학년도 명단 스냅샷 생성
3. 다음 학년도 교실 자동 복제(학생은 선택적 복제)
4. 기존 학년도 학급은 `is_active=False`로 전환
5. 서비스별 화면은 기본적으로 `is_active=True`만 표시

복구:
- 스냅샷 기준으로 특정 시점 복원 가능

---

## 8) API/서비스 계층 설계

`roster/services.py` 권장 함수:

- `get_active_classrooms(user)`
- `get_students_for_classroom(user, classroom_id)`
- `resolve_active_classroom_from_session(request)`
- `clone_school_year(user, from_year, to_year, with_students=False)`

원칙:
- 뷰에서 직접 복잡한 쿼리 작성 금지
- 서비스 함수 단위 테스트 우선

---

## 9) 마이그레이션/배포 전략

1. 스키마 추가 (읽기 영향 없음)
2. 백필 스크립트로 기존 데이터 매핑
3. 기능 플래그 `ROSTER_READ_ENABLED` 활성화(읽기만)
4. 운영 검증
5. `ROSTER_WRITE_ENABLED` 순차 활성화

롤백:
- 플래그 즉시 OFF로 기존 경로 복귀
- 데이터는 유지, 트래픽만 기존 모델로 전환

---

## 10) 검증 체크리스트

1. 학급 단축키 선택/해제 동작 유지
2. ppobgi 자동 채움 결과 일치(학생 수/순서)
3. studentmbti 세션 생성 시 학급 연결 정확
4. 학년도 전환 후 과거 결과/로그 조회 보존
5. 데이터 없는 교사는 선택기 미노출 유지

---

## 11) 일정 제안 (10일+)

1. Day 1-2: 모델/마이그레이션/서비스 계층 생성
2. Day 3-5: 백필 + 읽기 경로 연결 + 테스트
3. Day 6-7: 기능 플래그/운영 검증 도구
4. Day 8-10: 선택 서비스 쓰기 경로 전환 + 회귀 테스트
5. Day 11+: 모니터링/버그 수정

---

## 12) 운영 문구 가이드

- 금지: "학생 DB 구축", "신규 개인정보 수집"
- 권장: "기존 학급 정보를 빠르게 불러오는 단축키", "이미 입력한 명단 재사용"

---

## 결론

Phase 4는 반드시 진행할 가치가 있지만, 지금 즉시 개발보다
"학년도 전환 시점 + 읽기 우선 전환 + 기능 플래그" 전략으로 착수하는 것이 안전하다.
