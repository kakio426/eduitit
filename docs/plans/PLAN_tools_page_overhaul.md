# **Implementation Plan: Tools Page Overhaul**

Status: 🔄 In Progress  
Started: 2026-02-09  
Last Updated: 2026-02-09  
Estimated Completion: 2026-02-10  

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
현재 클라이언트 사이드 JS로 비효율적으로 관리되고 있는 `/tools/` 가이드 페이지를 Django 서버사이드 렌더링(SSR) 체제로 전환하고, 2026년 2월 기준 최신 AI 도구 추가 및 자동 업데이트 알림 기능을 도입합니다.

### **Success Criteria**
* [ ] **SEO 최적화**: 모든 도구 설명이 HTML 소스에 포함됨 (SSR)
* [ ] **관리 효율**: `core/data/tools.py` 수정만으로 도구 추가/수정 가능
* [ ] **UI/UX**: SIS 표준(Claymorphism, pt-32) 준수 및 부드러운 필터링
* [ ] **자동화**: 업데이트 날짜 기준 'NEW' 배지 자동 노출

### **User Impact**
* 선생님들이 최신 AI 도구 정보를 더 빠르고 정확하게 파악 가능
* 검색 엔진을 통한 서비스 노출 증가
* 저비용 고효율 운영 환경 구축

## **🏗️ Architecture Decisions**

| Decision | Rationale | Trade-offs |
| :---- | :---- | :---- |
| **Data in Python File** | 외부 도구 추천은 변경이 잦지 않고, DB 부하 없이 성능이 최고이며 버전 관리가 쉬움 | 운영자가 Admin UI가 아닌 코드를 수정해야 함 (사용자 개발자 환경 고려) |
| **SSR + Alpine.js** | 초기 렌더링은 SSR로 SEO를 챙기고, 필터링 등 상호작용은 Alpine.js로 끊김 없이 처리 | 데이터가 템플릿과 Alpine 스토어 양쪽에 존재할 수 있음 (JSON context 활용으로 해결) |
| **Automated New Badge** | 운영자가 수동으로 체크할 필요 없이 날짜 비교로만 제어하여 운영 리소스 절감 | 서버 시간 기준이므로 사용자별 다른 기준 적용 불가 (단순 정보성으론 충분) |

## **📦 Dependencies**

### **Required Before Starting**
* [x] `core` 앱 내 `templates/core/tool_guide.html` 존재 확인
* [x] `products` 모델 구조 이해 (참조용)

## **🧪 Test Strategy (Terminal First)**

### **Testing Approach**
TDD 원칙에 따라 데이터 로직과 뷰 컨텍스트 생성을 먼저 검증합니다. 브라우저 없이 터미널에서 데이터 무결성을 체크합니다.

### **Test Pyramid for This Feature**

| Test Type | Coverage Target | Tool & Env |
| :---- | :---- | :---- |
| **Unit Tests** | 데이터 구조 및 날짜 계산 로직 | Django Shell / Pytest (Terminal) |
| **Integration Tests** | 뷰 컨텍스트 데이터 전달 | Django Client Test (Terminal) |
| **E2E Tests** | 필터링 및 모달 작동 | Playwright (Final Phase / Headless) |

## **🚀 Implementation Phases**

### **Phase 1: Foundation - Data & View Logic**
Goal: 데이터를 파일로 분리하고 뷰에서 이를 올바르게 읽어오는지 확인
Verification Mode: 🖥️ TERMINAL ONLY
Status: ⏳ Pending

#### **Tasks**
**🔴 RED: Write Failing Tests First**
* [ ] **Test 1.1**: `tools.py`에서 데이터를 불러올 수 없는 상태에서 `tool_guide` 뷰 호출 시 빈 리스트 반환 확인
* [ ] **Test 1.2**: 특정 날짜 기준 `is_new` 필드가 올바르게 계산되는지 검증하는 단위 테스트 작성

**🟢 GREEN: Implement to Make Tests Pass**
* [ ] **Task 1.3**: `core/data/` 디렉토리 생성 및 `__init__.py` 추가
* [ ] **Task 1.4**: `core/data/tools.py` 생성 (기존 JS 데이터 이관 및 스키마 정의)
* [ ] **Task 1.5**: `core/views.py` 수정 (데이터 임포트 및 `is_new` 로직 포함하여 context 전달)

**🔵 REFACTOR: Clean Up Code**
* [ ] **Task 1.6**: 데이터 로딩 로직을 별도 유틸 함수로 분리 고려

#### **Quality Gate ✋**
* [ ] `python manage.py shell`에서 `TOOLS_DATA`가 정상적으로 로드됨
* [ ] 뷰 호출 시 context에 `tools` 리스트가 포함됨

---

### **Phase 2: Content Enhancement & New Tools**
Goal: 모든 도구 설명을 SIS 표준에 맞게 보강하고 신규 툴 5종 이상 추가
Verification Mode: 🖥️ TERMINAL ONLY
Status: ⏳ Pending

#### **Tasks**
* [ ] **Task 2.1**: 기존 30여 개 도구 설명 보강 (Lead Text, 3개 이상의 Features)
* [ ] **Task 2.2**: **Figma**, **Sentry**, **Supabase**, **V0.dev**, **Cursor** 최신 정보 업데이트
* [ ] **Task 2.3**: `last_updated` 날짜를 2026-02-09 전후로 설정

---

### **Phase 3: Template Overhaul (SSR + Alpine.js)**
Goal: 기존 JS 렌더링을 제거하고 SSR 렌더링 + Alpine 필터링 적용
Verification Mode: 🧪 JSDOM / HEADLESS
Status: ⏳ Pending

#### **Tasks**
* [ ] **Task 3.1**: `tool_guide.html`의 `<script>` 데이터 제거
* [ ] **Task 3.2**: `{% for %}` 루프로 카드 레이아웃 구현 (Claymorphism 적용)
* [ ] **Task 3.3**: Alpine.js `x-data`, `x-show`를 이용한 카테고리 필터링 구현
* [ ] **Task 3.4**: SSR 환경에서의 모달 컨텐츠 렌더링 구현

---

### **Phase 4: Final Verification & Mobile Optimization**
Goal: 모바일 뷰 최적화 및 전체 바이브 체크
Verification Mode: ⚠️ BROWSER ALLOWED
Status: ⏳ Pending

#### **Tasks**
* [ ] **Task 4.1**: 320px 환경에서 카드 및 모달 레이아웃 정합성 확인
* [ ] **Task 4.2**: 폰트(나눔스퀘어라운드) 및 컬러(SIS 표준) 최종 검점
* [ ] **Task 4.3**: 디버그 로그 및 미사용 코드 정리

## **⚠️ Risk Assessment**
| Risk | Probability | Impact | Mitigation Strategy |
| :---- | :---- | :---- | :---- |
| 데이터 파일 구문 오류 | Low | High | `python manage.py check` 생활화 및 쉘 검증 필수 |
| Alpine.js 초기화 지연으로 필터링 미작동 | Low | Medium | SSR로 기본 리스트를 먼저 보여주어 사용자 경험 보존 |

## **🔄 Rollback Strategy**
### **If Failure Occurs**
* `git checkout core/templates/core/tool_guide.html` (기존 JS 방식 복구)
* `core/data/` 폴더 삭제 및 `views.py` 원복

## **📊 Progress Tracking**
* **Phase 1**: ⏳ 0%
* **Phase 2**: ⏳ 0%
* **Phase 3**: ⏳ 0%
* **Overall Progress**: 0% complete
