# Implementation Plan: Comprehensive Multi-School Reservation System (reservations)

**Status:** 🔄 In Progress
**Started:** 2026-02-12
**Last Updated:** 2026-02-12
**Estimated Completion:** 2026-02-16

⚠️ **CRITICAL INSTRUCTIONS:** After completing each phase:
- ✅ Check off completed task checkboxes
- 🧪 Run all quality gate validation commands
- ⚠️ Verify ALL quality gate items pass
- 📅 Update "Last Updated" date above
- 📝 Document learnings in Notes section
- ➡️ Only then proceed to next phase
- ⛔ DO NOT skip quality gates or proceed with failing checks

---

## 📋 Overview

### Feature Description
A multi-tenant reservation system balancing Administrator Sovereignty and User Convenience.
- **Admin:** 학교별 고유 링크, 교시 설정(1~N교시), 블랙아웃(예약 금지) 기간 설정, 예약 강제 수정/삭제 권한.
- **User (Guest):** 반응형 UI(PC 타임라인/모바일 리스트), 양보 요청, '내 예약' 트래커(LocalStorage), 한 줄 메모.
- **Vibe:** 신뢰 기반, 실시간 업데이트, 관리자 중심의 유연한 운영.

### Success Criteria
- [ ] **Multi-Tenancy:** `/reservations/<school-slug>/` 기반의 완벽한 데이터 격리.
- [ ] **Admin Sovereignty:** 관리자가 모든 예약 제어 및 학교별 환경(교시, 예약 가능 기간 등) 설정 가능.
- [ ] **Real-time Sync:** HTMX Polling(30s)을 통한 실시간 예약 현황 동기화.
- [ ] **Navigation:** 공용 화면 ↔ 관리자 대시보드 ↔ 메인 홈 간의 유기적 이동 경로 확보.
- [ ] **SIS Compliance:** AI 로깅, Claymorphism 디자인, Admin 최적화 준수.

---

## 🏗️ Architecture Decisions

| Decision | Rationale | Trade-offs |
| :--- | :--- | :--- |
| **Slug-based Routing** | 학교별 독립된 공간 제공 (`/reservations/seoul-es/`). | 슬러그 중복 체크 로직 필요. |
| **LocalStorage Tracker** | 로그인 없이 '내가 한 예약'만 모아보기 위해 브라우저 저장소 활용. | 브라우저 데이터 삭제 시 초기화되나 게스트 환경에 최적. |
| **HTMX Polling** | 실시간성 확보를 위해 30초 간격으로 시간표 부분 갱신. | 서버 트래픽이 약간 증가하나 데이터 정합성 보장. |
| **Optimistic Locking** | 예약 생성 시점의 충돌 방지를 위해 DB 트랜잭션/View 레벨 체크. | 사용자에게 "이미 예약됨" 에러 메시지 노출 가능성. |

---

## 🚀 Implementation Phases

### Phase 1: Multi-School Foundation (Models & Config)
**Goal:** 학교별 독립 환경 및 관리자 설정을 위한 데이터 구조 구축 (SIS/CLAUDE 규격 준수).

- [x] **Task 1.1:** Models: `School` (slug, owner), `SpecialRoom`, `SchoolConfig` (교시 수, 예약 가능 기간).
- [x] **Task 1.2:** Models: `Reservation` (메모 필드), `RecurringSchedule` (고정 수업), `BlackoutDate`.
- [x] **Task 1.3:** Admin Optimization: `ReservationAdmin` 등에 `list_display` FK 사용 시 `select_related` 적용 (CLAUDE #14).
- [x] **Task 1.4:** `ensure_reservations` 커맨드 생성.
    - *주의:* `service_type` 등 Admin 관리 필드는 생성 시에만 설정하고, 업데이트 시 덮어쓰지 않도록 조건 처리 (CLAUDE #30).

**Quality Gate:** `python manage.py check` 통과 및 Admin에서 N+1 쿼리 발생 안 함.

### Phase 2: Power Admin Dashboard & Navigation
**Goal:** 학교 관리자를 위한 "미션 컨트롤" 센터 및 네비게이션 구축.

- [x] **Task 2.1:** Dashboard UI: `clay-card` 적용 및 상단 `pt-32` 준수 (CLAUDE UI Standard).
    - **Navigation:** "내 학교 바로가기(Public View)" 버튼 및 "홈으로" 버튼 필수 배치.
- [x] **Task 2.2:** Schedule Matrix: 드래그/클릭으로 고정 수업(Recurring) 설정 그리드.
- [x] **Task 2.3:** Blackout Manager: 시험/방학 기간 설정 UI.
- [x] **Task 2.4:** Admin Override: 예약 강제 삭제/수정 기능. (Phase 3 예약 현황판에서 구현)
    - **Logging:** 관리자 강제 조치 시 `logger.info("[Reservation] Action: ADMIN_OVERRIDE ...")` 기록 (SIS #40).

### Phase 3: Responsive User Booking (PC/Mobile)
    - 예약된 칸 클릭 → 양보 사유 모달.
    - 기존 예약자 승인 시 소유권 이전.
    - **Logging:** `logger.info("[Reservation] Action: SWAP_REQUEST/APPROVE ...")` 기록.
- [ ] **Task 4.2:** QR Generator: `qrcode` 라이브러리 사용 (`requirements.txt` 추가 필수).
    - 대시보드에서 각 교실별 QR 다운로드/인쇄 페이지 제공.
- [ ] **Task 4.3:** Deployment Prep:
    - `settings_production.py`의 `INSTALLED_APPS` 및 `run_startup_tasks`에 등록.
    - `Procfile` 및 `nixpacks.toml` 동기화.
    - `preview_modal.html`에 `reservations` 시작 버튼 링크 연결 (CLAUDE #31).

---

## 📊 Progress Tracking

- **Phase 1:** ✅ 100%
- **Phase 2:** ✅ 100%
- **Phase 3:** ✅ 100%
- **Phase 4:** ✅ 90%

---
## 📝 Notes & Learnings
*(Document any deviations from plan or interesting technical discoveries here)*
