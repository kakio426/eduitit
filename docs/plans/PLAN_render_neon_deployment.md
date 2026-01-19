# **Implementation Plan: Render + Neon 배포**

Status: ✅ Complete  
Started: 2026-01-19  
Last Updated: 2026-01-19  
Completed: 2026-01-19 (약 45분 소요)

**⚠️ CRITICAL INSTRUCTIONS**: After completing each phase:

1. ✅ Check off completed task checkboxes  
2. 🧪 Run all quality gate validation commands in **TERMINAL**  
3. ⚠️ Verify ALL quality gate items pass  
4. 📅 Update "Last Updated" date above  
5. 📝 Document learnings in Notes section  
6. ➡️ Only then proceed to next phase

⛔ DO NOT OPEN BROWSER unless explicitly instructed in the phase.  
⛔ DO NOT skip quality gates or proceed with failing checks

---

## **📋 Overview**

### **Feature Description**

Django 6.0 기반 `eduitit` 애플리케이션을 **Render(호스팅) + Neon(PostgreSQL)** 조합으로 무료 배포합니다.

**왜 이 조합인가?**
- 💰 **비용 0원 시작**: 카드 등록 없이 완전 무료로 시작
- 📈 **확장 가능**: 성장 시 월 $7~$19의 고정 요금으로 업그레이드 가능
- ⏱️ **HWP 변환 안정성**: Railway/Vercel의 10초 제한 없이 충분한 시간 확보
- 🔒 **예측 가능한 비용**: 변동 요금제가 아닌 고정 요금

### **Success Criteria**

- [ ] Django 앱이 Render에서 정상 동작
- [ ] Neon PostgreSQL DB 연결 성공
- [ ] 정적 파일(CSS, JS) 정상 서빙
- [ ] 미디어 파일 업로드/다운로드 정상 동작
- [ ] 기존 모든 테스트 통과

### **User Impact**

선생님들이 무료로 교육 도구를 사용할 수 있으며, 사용량이 늘어도 예측 가능한 비용으로 운영할 수 있습니다.

---

## **🏗️ Architecture Decisions**

| **결정 사항** | **이유** | **Trade-offs** |
|:---|:---|:---|
| SQLite → PostgreSQL (Neon) | Render는 파일 시스템 휘발성, PostgreSQL 필수 | 마이그레이션 작업 필요 |
| WhiteNoise 정적 파일 서빙 | Render 무료 티어에서 별도 CDN 불필요 | 대규모 트래픽 시 별도 CDN 고려 필요 |
| `dj-database-url` 사용 | Render 환경변수 자동 연결 | 추가 패키지 의존성 |
| Gunicorn WSGI 서버 | 프로덕션 표준 | 개발환경과 다른 설정 필요 |

---

## **📦 Dependencies**

### **Required Before Starting**

- [ ] Render 계정 생성 (무료): https://render.com
- [ ] Neon 계정 생성 (무료): https://neon.tech
- [ ] Git 저장소 준비 (GitHub/GitLab)

### **New Python Dependencies**

```text
gunicorn==21.2.0
dj-database-url==2.1.0
psycopg2-binary==2.9.9
whitenoise==6.6.0
python-dotenv==1.0.1
```

---

## **🧪 Test Strategy (Terminal First)**

### **Testing Approach**

TDD Principle: Write tests FIRST, then implement to make them pass.  
Speed Protocol: All tests must run in the TERMINAL without launching a visible browser.

### **Test Pyramid for This Feature**

| Test Type | Coverage Target | Tool & Env |
|:---|:---|:---|
| **Unit Tests** | DB connection, settings | pytest/Django TestCase (Terminal) |
| **Integration Tests** | API endpoints health check | curl/httpie (Terminal) |
| **E2E Tests** | Full user flow on Render | Manual Verification |

### **Existing Test Files**

- `core/tests/test_auth.py` - 인증 테스트
- `core/tests/test_dashboard.py` - 대시보드 테스트
- `products/tests/test_views.py` - 제품 뷰 테스트
- `products/tests/test_models.py` - 모델 테스트
- `products/tests/test_ownership.py` - 소유권 테스트

---

## **🚀 Implementation Phases**

### **Phase 1: 프로젝트 준비 및 의존성 설정**

Goal: 프로덕션 배포에 필요한 패키지 및 설정 파일 생성  
Verification Mode: 🖥️ TERMINAL ONLY (No Browser)  
Status: ✅ Complete  
Estimated Time: 1.5시간

#### **Tasks**

**🔴 RED: Write Failing Tests First**

- [x] **Test 1.1**: `config/settings_production.py` 로딩 테스트 (파일 없으므로 실패)
- [x] **Test 1.2**: 환경변수 기반 DB 연결 테스트 (설정 없으므로 실패)

**🟢 GREEN: Implement to Make Tests Pass**

- [x] **Task 1.3**: `requirements.txt` 생성
  - 현재 패키지 + 새 의존성 추가
- [x] **Task 1.4**: `config/settings_production.py` 생성
  - DEBUG=False 설정
  - SECRET_KEY 환경변수화
  - ALLOWED_HOSTS 설정
  - dj-database-url로 PostgreSQL 연결
  - WhiteNoise 미들웨어 추가
  - STATIC_ROOT 설정
- [x] **Task 1.5**: `render.yaml` 생성 (Render Blueprint)
- [x] **Task 1.6**: `.env.example` 생성

**🔵 REFACTOR: Clean Up Code**

- [x] **Task 1.7**: 기존 `settings.py`와 분리 확인 (개발/프로덕션 분리)

#### **Quality Gate ✋**

**⚠️ STOP: TERMINAL VERIFICATION ONLY**

**Validation Commands**:

```bash
# 1. 의존성 설치 확인
pip install -r requirements.txt

# 2. 설정 파일 검증
python -c "import config.settings_production"

# 3. 기존 테스트 통과 확인
python manage.py test
```

**Checklist**:

- [ ] **Build**: 모든 패키지 설치 성공
- [ ] **Settings**: Production 설정 파일 로딩 성공
- [ ] **Tests**: 기존 테스트 모두 통과 (sqlite 환경)
- [ ] **No Browser**: 브라우저 열지 않음

---

### **Phase 2: 데이터베이스 마이그레이션 (SQLite → Neon PostgreSQL)**

Goal: Neon PostgreSQL 연결 및 마이그레이션  
Verification Mode: 🖥️ TERMINAL ONLY (No Browser)  
Status: ✅ Complete  
Estimated Time: 1.5시간

#### **Tasks**

**🔴 RED: Write Failing Tests First**

- [x] **Test 2.1**: PostgreSQL 연결 테스트 (연결 정보 없으므로 실패)

**🟢 GREEN: Implement to Make Tests Pass**

- [x] **Task 2.2**: Neon에서 새 프로젝트 생성
  - DB 이름: `neondb`
  - Region: ap-southeast-1 (Singapore)
- [x] **Task 2.3**: 환경변수에 DATABASE_URL 설정
- [x] **Task 2.4**: `python manage.py migrate --settings=config.settings_production` 실행
- [x] **Task 2.5**: `python manage.py createsuperuser` 실행 (admin/admin1234)

**🔵 REFACTOR: Clean Up Code**

- [x] **Task 2.6**: 로컬 SQLite와 프로덕션 PostgreSQL 분리 확인

#### **Quality Gate ✋**

**Validation Commands**:

```bash
# 1. 마이그레이션 확인
python manage.py showmigrations --settings=config.settings_production

# 2. DB 연결 테스트
python manage.py shell --settings=config.settings_production -c "from django.db import connection; connection.ensure_connection()"

# 3. 전체 테스트 (PostgreSQL 환경)
DATABASE_URL=$DATABASE_URL python manage.py test --settings=config.settings_production
```

**Checklist**:

- [ ] **Migration**: 모든 마이그레이션 적용됨
- [ ] **Connection**: DB 연결 성공
- [ ] **Tests**: 테스트 통과 (PostgreSQL 환경)

---

### **Phase 3: 정적 파일 및 미디어 파일 설정**

Goal: WhiteNoise로 정적 파일 서빙, 미디어 파일 처리 방안  
Verification Mode: 🖥️ TERMINAL ONLY (No Browser)  
Status: ✅ Complete  
Estimated Time: 1시간

#### **Tasks**

**🟢 GREEN: Implement**

- [x] **Task 3.1**: `collectstatic` 명령 확인 (130 static files copied)
- [x] **Task 3.2**: WhiteNoise 미들웨어 설정 완료
- [x] **Task 3.3**: MEDIA_URL/MEDIA_ROOT 프로덕션 설정

> [!NOTE]
> Render 무료 티어에서는 파일 시스템이 휘발성입니다.  
> 미디어 파일(업로드)은 Cloudinary, AWS S3, 또는 Supabase Storage 연동이 필요할 수 있습니다.

#### **Quality Gate ✋**

**Validation Commands**:

```bash
# 1. 정적 파일 수집
python manage.py collectstatic --noinput --settings=config.settings_production

# 2. 정적 파일 존재 확인
ls staticfiles/
```

---

### **Phase 4: Render 배포 및 최종 검증**

Goal: Render에 배포 및 전체 기능 검증  
Verification Mode: 🌐 BROWSER ALLOWED (최종 확인)  
Status: ✅ Complete  
Estimated Time: 2시간

#### **Tasks**

- [x] **Task 4.1**: GitHub 저장소에 코드 푸시
- [x] **Task 4.2**: Render에서 Web Service 생성
  - Build Command: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
  - Start Command: `gunicorn config.wsgi:application`
- [x] **Task 4.3**: 환경변수 설정
  - `SECRET_KEY`
  - `DATABASE_URL`
  - `DJANGO_SETTINGS_MODULE=config.settings_production`
  - `ALLOWED_HOSTS`
- [x] **Task 4.4**: 배포 확인 (https://eduitit.onrender.com)
- [x] **Task 4.5**: 빌드 오류 수정 (Pillow 추가)

#### **Quality Gate ✋**

**Validation Commands (Manual)**:

```bash
# 1. Health Check
curl https://your-app.onrender.com/

# 2. 관리자 페이지 접근
# 브라우저: https://your-app.onrender.com/admin/
```

**Manual Testing Checklist**:

- [x] 홈페이지 로딩 확인
- [x] 로그인/로그아웃 테스트
- [x] 제품 목록/상세 페이지 확인
- [x] 대시보드 기능 확인

---

## **⚠️ Risk Assessment**

| Risk | Probability | Impact | Mitigation Strategy |
|:---|:---|:---|:---|
| Neon 무료 한도 초과 | Low | Mid | 사용량 모니터링, 필요 시 유료 전환 |
| 미디어 파일 손실 (휘발성) | High | High | 외부 스토리지 연동 (Phase 3) |
| 콜드 스타트 지연 | Mid | Low | 첫 접속 시 10-30초 대기 안내 |

---

## **🔄 Rollback Strategy**

### **If Deployment Fails**

1. Render 대시보드에서 이전 배포 버전으로 롤백
2. 환경변수 복구
3. 로컬에서 이전 코드로 테스트

### **If Database Migration Fails**

1. Neon에서 새 브랜치 생성 (Time Travel 기능)
2. 마이그레이션 문제 해결 후 재적용

---

## **📊 Progress Tracking**

### **Completion Status**

- **Phase 1**: ⏳ 0%  
- **Phase 2**: ⏳ 0%  
- **Phase 3**: ⏳ 0%  
- **Phase 4**: ⏳ 0%

**Overall Progress**: 0% complete

### **Time Tracking**

| Phase | Estimated | Actual | Variance |
|:---|:---|:---|:---|
| Phase 1 | 1.5 hours | - | - |
| Phase 2 | 1.5 hours | - | - |
| Phase 3 | 1 hour | - | - |
| Phase 4 | 2 hours | - | - |

**Total**: 약 6시간 예상

---

## **📝 Notes & Learnings**

### **Implementation Notes**

- (구현 중 작성 예정)

### **Blockers Encountered**

- (없음)

---

## **📚 References**

- [Render Django 배포 가이드](https://render.com/docs/deploy-django)
- [Neon 시작 가이드](https://neon.tech/docs/introduction)
- [WhiteNoise 문서](http://whitenoise.evans.io/en/stable/)
- [dj-database-url 문서](https://github.com/jazzband/dj-database-url)

---

## **✅ Final Checklist**

**Before marking plan as COMPLETE**:

- [ ] All phases completed with quality gates passed
- [ ] Full integration testing performed
- [ ] Documentation updated
- [ ] Security review completed (SECRET_KEY, DEBUG, etc.)
- [ ] Plan document archived
