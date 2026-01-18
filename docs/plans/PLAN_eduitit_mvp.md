# Implementation Plan: Eduitit MVP Setup & Service Listing

**Status**: ⏳ Pending Approval
**Estimated Completion**: 2-3 Days (Total 8-10 Hours work)

---

**⚠️ CRITICAL INSTRUCTIONS**: 각 단계(Phase)가 끝난 후 반드시 다음을 수행해야 합니다:

1. ✅ 완료된 작업 체크박스 표시
2. 🧪 모든 품질 게이트(Quality Gate) 검증 명령어 실행
3. ⚠️ 모든 품질 게이트 항목이 통과했는지 확인
4. 📝 Notes 섹션에 배운 점 기록
5. ➡️ 그 후 다음 단계로 진행

⛔ **품질 게이트를 통과하지 못하면 절대 다음 단계로 넘어가지 마십시오.**

---

## 📋 Overview

### Feature Description

'eduitit'이라는 브랜드로 개인 포트폴리오 및 자체 개발한 서비스(HWP-PDF 변환기, 기사 자동 제작 등)를 소개하고 판매할 수 있는 웹 플랫폼의 기초를 구축합니다. Antigravity를 활용하여 기본 랜딩 페이지와 데이터베이스에 등록된 서비스 목록을 보여주는 기능을 구현합니다.

### Success Criteria

* [x] Antigravity 기반 프로젝트가 로컬에서 구동되어야 함
* [x] 관리자 페이지(Admin)에서 서비스(Service) 항목을 등록/수정할 수 있어야 함
* [x] 메인 페이지 또는 별도 페이지에서 등록된 서비스 목록이 카드 형태로 표시되어야 함
* [x] 각 서비스 클릭 시 상세 페이지로 이동해야 함

### User Impact

사용자는 즉시 자신의 웹사이트에 접속하여 본인의 포트폴리오와 판매할 툴들을 관리하고 방문자에게 보여줄 수 있게 됩니다.

---

## 🏗️ Architecture Decisions

| Decision | Rationale | Trade-offs |
| --- | --- | --- |
| **Antigravity Boilerplate** | 빠른 SaaS 구축, 인증/결제 등 기반 기능 활용 | 초기 학습 곡선 및 커스터마이징 제약 |
| **PostgreSQL** | 안정적인 데이터 관리 및 배포 환경 호환성 | SQLite 대비 설정 복잡도 약간 상승 |
| **Server-Side Rendering (Templates)** | 빠른 개발 속도 및 SEO 최적화 (포트폴리오 특성상 중요) | React/Vue 대비 동적 인터랙션 구현 시 코드량 증가 |

---

## 📦 Dependencies

### Required Before Starting

* [ ] Python 환경 설정 (Virtualenv / Poetry)
* [ ] Docker 및 Docker Compose (DB 구동용)
* [ ] Antigravity 라이선스 및 초기 코드

---

## 🧪 Test Strategy

### Testing Approach

**TDD Principle**: 모델과 뷰의 동작을 정의하는 테스트를 먼저 작성하고 구현합니다.

### Test Pyramid for This Feature

| Test Type | Coverage Target | Purpose |
| --- | --- | --- |
| **Unit Tests** | ≥80% | 서비스(Product) 모델 데이터 무결성 검증 |
| **Integration Tests** | Critical paths | URL 라우팅 및 템플릿 렌더링 검증 |

---

## 🚀 Implementation Phases

### Phase 1: Project Foundation & Landing Page

**Goal**: Antigravity 프로젝트 초기화 및 기본 랜딩 페이지가 정상 동작하는지 확인
**Estimated Time**: 2 Hours
**Status**: ⏳ Pending

#### Tasks

**🔴 RED: Write Failing Tests First**

* [ ] **Test 1.1**: 메인 페이지 URL 접속 테스트
* File: `tests/test_core_views.py`
* Expected: URL 설정이 아직 안 되었거나 뷰가 없어서 실패(404 or Error)해야 함
* Details: `/` 경로로 GET 요청 시 status code 200 확인



**🟢 GREEN: Implement to Make Tests Pass**

* [ ] **Task 1.2**: 환경 설정 및 서버 구동
* Details: `.env` 설정, Docker 컨테이너 실행 (`make docker-up` 등)


* [ ] **Task 1.3**: 기본 랜딩 페이지 라우팅 및 템플릿 연결
* Details: Antigravity 기본 홈 뷰 확인 및 텍스트를 "Eduitit - My Tools"로 변경



**🔵 REFACTOR: Clean Up Code**

* [ ] **Task 1.4**: 불필요한 기본 예제 코드 정리
* Details: Boilerplate에 포함된 사용하지 않는 예제 페이지 비활성화



#### Quality Gate ✋

* [ ] **Build**: 서버가 에러 없이 실행됨 (`python manage.py runserver`)
* [ ] **Tests**: 작성한 URL 테스트 통과
* [ ] **Manual**: 브라우저에서 `localhost:8000` 접속 시 "Eduitit" 문구 확인

---

### Phase 2: Service Model Implementation (Backend)

**Goal**: 판매/소개할 서비스(예: HWP변환기)를 저장할 데이터베이스 모델 구축
**Estimated Time**: 2-3 Hours
**Status**: ⏳ Pending

#### Tasks

**🔴 RED: Write Failing Tests First**

* [ ] **Test 2.1**: Product 모델 생성 및 속성 테스트
* File: `products/tests/test_models.py`
* Expected: `Product` 클래스가 없어서 ImportError 발생
* Details: `title`, `description`, `price`, `is_active` 필드를 가진 모델 인스턴스 생성 테스트



**🟢 GREEN: Implement to Make Tests Pass**

* [ ] **Task 2.2**: Product 앱 생성 및 모델 구현
* File: `products/models.py`
* Details: Django Model 상속받아 필드 구현


* [ ] **Task 2.3**: 데이터베이스 마이그레이션
* Details: `makemigrations` & `migrate`



**🔵 REFACTOR: Clean Up Code**

* [ ] **Task 2.4**: Admin 사이트 등록
* File: `products/admin.py`
* Details: 관리자 페이지에서 상품을 쉽게 등록하도록 설정



#### Quality Gate ✋

* [ ] **TDD Compliance**: 모델 클래스 작성 전 테스트 먼저 작성 확인
* [ ] **Tests**: 모델 생성 테스트 Pass
* [ ] **DB**: 마이그레이션 파일 생성 및 적용 완료

---

### Phase 3: Service Listing & Detail Views (Frontend)

**Goal**: 등록한 서비스를 사용자에게 보여주는 UI 구현
**Estimated Time**: 3-4 Hours
**Status**: ⏳ Pending

#### Tasks

**🔴 RED: Write Failing Tests First**

* [ ] **Test 3.1**: 서비스 목록 페이지 뷰 테스트
* File: `products/tests/test_views.py`
* Details: `/products/` 접속 시 등록된 상품 제목이 HTML에 포함되어 있는지 확인


* [ ] **Test 3.2**: 서비스 상세 페이지 뷰 테스트
* Details: `/products/<id>/` 접속 시 해당 상품 설명이 보이는지 확인



**🟢 GREEN: Implement to Make Tests Pass**

* [ ] **Task 3.3**: 서비스 목록(List) 뷰 및 템플릿 구현
* File: `products/views.py`, `templates/products/list.html`
* Details: DB에서 `is_active=True`인 상품만 쿼리하여 카드 리스트로 출력


* [ ] **Task 3.4**: 서비스 상세(Detail) 뷰 및 템플릿 구현
* File: `products/views.py`, `templates/products/detail.html`
* Details: 개별 상품 정보 표시 및 "사용하기/구매하기" 버튼(현재는 링크만) 배치



**🔵 REFACTOR: Clean Up Code**

* [ ] **Task 3.5**: UI 스타일링 (Bootstrap/Tailwind)
* Details: Antigravity의 기본 CSS 활용하여 깔끔하게 정리



#### Quality Gate ✋

* [ ] **Tests**: 목록/상세 페이지 테스트 All Pass
* [ ] **Manual**: 관리자 페이지에서 'HWP-PDF 변환기' 더미 데이터 등록 후 프론트엔드에서 노출 확인
* [ ] **Linting**: 코드 스타일 점검 (flake8/black)

---

## ⚠️ Risk Assessment

| Risk | Probability | Impact | Mitigation Strategy |
| --- | --- | --- | --- |
| **Boilerplate 복잡도** | Medium | Medium | Antigravity 문서를 꼼꼼히 참조하고 불필요한 기능은 초기에 건드리지 않음 |
| **디자인 시간 소요** | High | Low | 초기에는 디자인보다 '기능 동작'에 집중, 기본 템플릿 활용 |

---

## 🔄 Rollback Strategy

* **Phase 1 실패 시**: `git clean -fdx`로 초기화 후 환경 설정 재시도
* **Phase 2 실패 시**: `python manage.py migrate products zero`로 DB 롤백 후 모델 코드 수정
* **Phase 3 실패 시**: 뷰/템플릿 파일 삭제 및 이전 커밋으로 `git checkout`

---

## 📝 Notes & Learnings

*(작업 완료 후 작성)*
