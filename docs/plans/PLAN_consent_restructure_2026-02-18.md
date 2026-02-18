# Consent 재구조 계획 (2026-02-18)

## 목표
- `consent`를 `signatures`와 데이터/운영 관점에서 완전 분리한다.
- 배포 직후 마이그레이션 누락으로 인한 `500`을 원천 차단한다.
- 교사/학부모 플로우(업로드 -> 위치설정 -> 수신자 -> 본인확인 -> 서명)를 안정적으로 유지한다.

## 현재 확인된 리스크
- `consent/models.py`가 `signatures.consent_models`를 재노출하고 있어 앱 경계가 불명확하다.
- `signatures` 마이그레이션 미적용 시 `consent`에서 즉시 `OperationalError`가 발생한다.
- 파일 미리보기는 스토리지/CORS 환경에 따라 PDF 렌더 실패 가능성이 있다.

## 실행 단계

### Phase 0. 운영 안정화 (완료)
- 스키마 사전점검 유틸 추가: `consent/schema.py`
- 점검 관리명령 추가: `python manage.py check_consent_schema`
- 런타임 부트스트랩에 점검 단계 추가: `core/management/commands/bootstrap_runtime.py`
- `consent` 뷰에 스키마 가드 적용(500 -> 503 안내)
- 미리보기 소스 프록시 추가: `consent_document_source` (same-origin 경로)
- `consent` 한글 텍스트 UTF-8 복구

### Phase 1. 모델 소유권 분리
- `consent/models.py`에 실제 모델 정의를 이관한다.
- 테이블명은 임시로 기존 `signatures_*`를 유지해 운영 중단 없이 전환한다.
- `consent` 앱에 독립 마이그레이션 체인을 만든다.

### Phase 2. 테이블 네임스페이스 정리
- 신규 `consent_*` 테이블로 복제/이관 마이그레이션 작성.
- 데이터 백필 + 외래키 참조 전환 + 구테이블 read-only 기간 운영.
- 전환 검증 후 `signatures`의 consent 관련 모델 제거.

### Phase 3. 통합 경로 정리
- 상품 라우팅 조건문에서 타이틀 문자열 비교 의존을 제거한다.
- `Product`에 명시적 내부 라우팅 키(예: `route_name`)를 도입한다.
- `ensure_consent`는 문자열 강제 갱신이 아닌 존재 보장만 수행한다.

### Phase 4. 법적 고지/운영 정책 고정
- 법적 고지 기본문구 버전 관리(`consent_text_version`)를 운영 정책과 연결한다.
- 보관 기간, 파기 정책, IP/User-Agent 수집 목적을 관리자 화면/매뉴얼에 명시한다.
- 감사로그 다운로드(요약 CSV/PDF)를 추가해 학교 감사 대응성을 높인다.

## 검증 기준 (각 단계 공통)
- `python manage.py check`
- `python manage.py check_consent_schema`
- `python manage.py test consent -v 2`
- 회귀: `python manage.py test collect.tests.test_collect_flow signatures -v 2`
- 수동 QA:
  - Step1 업로드 성공/실패 메시지 확인
  - Step2 PDF 미리보기 및 좌표 저장
  - Step3 수신자 등록/발송 링크 생성
  - 모바일 서명 제출/완료 후 통합 PDF 다운로드

## 롤백 원칙
- Phase 1~2는 항상 역마이그레이션 스크립트를 동반한다.
- 라우팅 전환은 feature flag로 감싼다.
- 스키마 점검 실패 시 서비스는 503 안내 화면으로 고정해 잘못된 데이터 생성을 막는다.
