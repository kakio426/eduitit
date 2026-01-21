# **Implementation Plan: Eduitit Expert Portfolio Upgrade**

Status: 🔄 In Progress  
Started: 2026-01-21  
Last Updated: 2026-01-21  
Estimated Completion: 2026-01-24  

**⚠️ CRITICAL INSTRUCTIONS**: After completing each phase:

1. ✅ Check off completed task checkboxes  
2. 🧪 Run all quality gate validation commands in **TERMINAL**  
3. ⚠️ Verify ALL quality gate items pass  
4. 📅 Update "Last Updated" date above  
5. 📝 Document learnings in Notes section  
6. ➡️ Only then proceed to next phase

⛔ DO NOT OPEN BROWSER unless explicitly instructed in the phase.  
⛔ DO NOT skip quality gates or proceed with failing checks

## **📋 Overview**

### **Feature Description**

에듀티잇(Eduitit)을 단순 '도구 모음'에서 '전문가 포트폴리오 플랫폼'으로 전환합니다. 현재 부족한 강의 이력 대신 **'공모전 입상 기록 및 수상 실적(Achievements)'**을 전면에 내세워 신뢰도를 구축하고, 향후 확장될 강의 커리큘럼과 개발기(DevLog)를 통합 관리하는 시스템을 구축합니다.

### **Success Criteria**

* [ ] **Achievement System**: 공모전 수상 실적 등을 관리하고 시각적으로 보여주는 기능 구현
* [ ] **Expert Profile**: 입상 기록, 기술 스택, 교육 철학을 한눈에 보여주는 매력적인 프로필 페이지
* [ ] **DevLog (Vibe Coding)**: 기술적 인사이트를 코드 하이라이팅과 함께 제공하는 상세 페이지 구현
* [ ] **Lecture & Inquiry**: (미래 대비) 강의 커리큘럼 등록 및 직접 섭외 요청 폼 구축
* [ ] **Trust UI**: 블루/퍼플 톤의 신뢰감 있는 Claymorphism 디자인 적용

### **User Impact**

* **방문자**: 강사의 실질적인 수상 실적을 통해 전문성을 즉각 확인하고 신뢰를 가짐.
* **사용자(선생님)**: 자신의 성과(입상 기록)를 체계적으로 아카이브하고 브랜드화하여 외부 섭외로 연결.

## **🏗️ Architecture Decisions**

| Decision | Rationale | Trade-offs |
| :---- | :---- | :---- |
| **App Name: `portfolio`** | 'Lecture'보다 포괄적인 'Portfolio'로 명명하여 수상 실적, 프로젝트, 강의를 통합 관리 | 기존 `lectures` 앱은 삭제 또는 통합 필요 |
| **Model: `Achievement` 추가** | 사용자의 요청대로 강의 이력 대신 현재의 강력한 무기인 '입상 기록'을 메인으로 활용 | 강의 기록 필드(`LectureHistory`)는 부가적으로 유지 |
| **Prism.js Integration** | DevLog에서 코드 스니펫을 유려하게 보여주어 '개발하는 전문가' 이미지 강화 | 클라이언트 사이드 라이브러리 추가 필요 |
| **Claymorphism (Blue/Purple)** | 전문가의 신뢰감을 주면서도 기존 사이트의 부드러운 감성 유지 | 다크 모드 등 색상 대비 세밀한 조정 필요 |

## **🧪 Test Strategy (Terminal First)**

### **Testing Approach**

TDD 원칙에 따라 테스트를 먼저 작성하고 구현합니다. 모든 검증은 터미널에서 수행하며, 최종 UI 연동 단계에서만 브라우저를 사용합니다.

### **Test Pyramid for This Feature**

| Test Type | Coverage Target | Tool & Env |
| :---- | :---- | :---- |
| **Unit Tests** | ≥80% | Pytest / Django TestClient (Terminal) |
| **Integration Tests** | Critical paths (Form submission) | Django TestClient / Curl (Terminal) |
| **E2E Tests** | Key user flows | Playwright (Headless Mode) - Phase 5 이후 |

## **🚀 Implementation Phases**

### **Phase 1: Foundation & Achievement Model**

Goal: 수상 실적(Achievement) 관리 및 기본 데이터 구조 구축  
Verification Mode: 🖥️ TERMINAL ONLY (No Browser)  
Status: 🔄 In Progress

#### **Tasks**

**🔴 RED: Write Failing Tests First**

* [ ] **Test 1.1**: `Achievement` 모델 CRUD 유닛 테스트 작성
* [ ] **Test 1.2**: `LectureProgram` & `Inquiry` 모델 기본 테스트 작성

**🟢 GREEN: Implement to Make Tests Pass**

* [ ] **Task 1.3**: `portfolio` 앱 생성 및 등록 (기존 `lectures` 관련 정리)
* [ ] **Task 1.4**: `Achievement`, `LectureProgram`, `LectureHistory`, `Inquiry` 모델 구현
* [ ] **Task 1.5**: DB 마이그레이션 실행

**🔵 REFACTOR: Clean Up Code**

* [ ] **Task 1.6**: Admin 페이지 등록 및 한국어 필드명(verbose_name) 정리

---

### **Phase 2: Portfolio & Inquiry Logic**

Goal: 데이터 관리 및 폼 처리 로직 구현  
Verification Mode: 🖥️ TERMINAL ONLY (No Browser)  
Status: ⏳ Pending

#### **Tasks**

**🔴 RED: Write Failing Tests First**

* [ ] **Test 2.1**: Inquiry(섭외 요청) 폼 유효성 검사 및 저장 테스트 작성
* [ ] **Test 2.2**: 포트폴리오 목록/상세 API/View 데이터 조회 테스트

**🟢 GREEN: Implement to Make Tests Pass**

* [ ] **Task 2.3**: `InquiryForm` 구현
* [ ] **Task 2.4**: `PortfolioView` (Achievement + Program) 로직 구현

**🔵 REFACTOR: Clean Up Code**

* [ ] **Task 2.5**: View 로직 최적화 및 에러 핸들링 보강

---

### **Phase 3: DevLog Expansion & Code Highlighting**

Goal: 기술 블로그 상세 페이지 및 코드 하이라이팅 적용  
Verification Mode: 🖥️ TERMINAL ONLY (Backend Logic)  
Status: ⏳ Pending

#### **Tasks**

* [ ] **Task 3.1**: `Insights` 모델 카테고리 필드 추가 및 리팩토링
* [ ] **Task 3.2**: 기술 블로그 상세 View 구현
* [ ] **Task 3.3**: Prism.js 적용 준비 (CSS/JS 정적 파일 배치)

---

### **Phase 4: Expert Branding UI (Profile & Portfolio)**

Goal: 블루/퍼플 톤의 프로필 및 포트폴리오 UI 구현  
Verification Mode: 🧪 JSDOM / MANUAL (Visual Check)  
Status: ⏳ Pending

#### **Tasks**

* [ ] **Task 4.1**: `about.html` (Hero, Stats with Counter Animation, Tech Stack)
* [ ] **Task 4.2**: `portfolio_list.html` (입상 기록 및 강의 목록 섹션 구분)
* [ ] **Task 4.3**: `inquiry_form.html` 테마 적용

---

## **⚠️ Risk Assessment**

| Risk | Probability | Impact | Mitigation Strategy |
| :---- | :---- | :---- | :---- |
| 콘텐츠 부족 (강의 이력) | High | Med | **입상 기록(Achievement)**을 전면에 배치하여 전문성 보완 |
| UI/UX 복잡도 증가 | Med | Med | Claymorphism 원칙을 유지하며 블루/퍼플 컬러 포인트만 활용 |
| 이메일 알림 연동 (Optional) | Med | Low | 우선 Admin 관리로 구현 후 필요 시 SMTP 설정 안내 |

## **🔄 Rollback Strategy**

### **If Phase 1 Fails**
* `portfolio` 앱 디렉토리 삭제
* `config/settings.py`의 `INSTALLED_APPS` 복구
* 마이그레이션 파일 삭제 및 DB 복구

## **📊 Progress Tracking**

### **Completion Status**
* **Phase 1**: 🔄 20%
* **Phase 2**: ⏳ 0%
* **Overall Progress**: 5%

## **📝 Notes & Learnings**
* 사용자는 현재 강의 실적보다 **수상 실적**이 강력하므로 이를 최상단에 배치하고 "신뢰"를 주는 것이 핵심임.
* `lectures`라는 좁은 범주보다 `portfolio`라는 넓은 범주가 향후 확장에 유리함.
