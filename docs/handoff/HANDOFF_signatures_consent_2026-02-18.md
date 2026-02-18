# Handoff: signatures 학교용 동의서 플로우 구축

**날짜**: 2026-02-18  
**상태**: MVP + 확장(위치설정 고도화) 완료  
**범위**: `signatures` 앱 내 독립 트랙(`/signatures/consent/`)

---

## 1) 배경/의사결정

- 기존 `signatures` 연수서명 기능은 유지.
- 학교용 학부모 동의서는 별도 메뉴/플로우로 분리.
- OTP는 제외, 대신 본인확인(이름 + 휴대폰 뒷4자리) + 감사로그 + PDF 증빙 강화.
- 교사용은 테이블 중심, 학부모는 3단계 위저드(본인확인 -> 동의/서명 -> 완료).

---

## 2) 구현 완료 내용

### A. 데이터 모델/마이그레이션

- 신규 모델 추가
  - `SignatureDocument`
  - `SignatureRequest`
  - `SignaturePosition`
  - `SignatureRecipient`
  - `ConsentAuditLog`
- 확장 필드
  - `SignatureRequest.preview_checked_at`
  - `SignaturePosition` 비율 좌표 필드
    - `x_ratio`, `y_ratio`, `w_ratio`, `h_ratio`
- 마이그레이션
  - `signatures/migrations/0007_signaturedocument_signaturerequest_and_more.py`
  - `signatures/migrations/0008_signatureposition_h_ratio_signatureposition_w_ratio_and_more.py`

### B. 백엔드 로직

- 파일: `signatures/consent_services.py`
- 구현:
  - PDF/이미지 문서 처리
  - 서명 레이어 합성
  - 감사 footer 삽입
  - 비동의 워터마크 삽입(`비동의`)
  - 통합 PDF 생성(학생명 가나다순)
  - 통합 PDF 옵션: `include_decline_summary=1` 시 비동의 사유 요약 페이지 추가
  - 위치 미리보기 PDF 생성

### C. 교사용 단계형 생성 플로우

- 파일: `signatures/consent_views.py`, `signatures/urls.py`
- 단계:
  1. 업로드/요청 기본정보
  2. 위치설정(pdf.js)
  3. 수신자 등록
- 발송 가드:
  - 위치 미리보기 확인(`preview_checked_at`) 전 발송 차단
  - 수신자 미등록 시 발송 차단

### D. 위치설정 UI

- 파일: `signatures/templates/signatures/consent/create_step2_positions.html`
- 기능:
  - pdf.js 기반 드래그 앤 드롭
  - 이미지 문서도 같은 화면에서 위치설정 가능
  - 페이지별 다중 서명 박스(추가/선택/삭제/리사이즈)
  - 서버 저장은 비율 좌표

### E. 화면/템플릿

- 신규 템플릿:
  - `signatures/templates/signatures/consent/dashboard.html`
  - `signatures/templates/signatures/consent/create_step1.html`
  - `signatures/templates/signatures/consent/create_step2_positions.html`
  - `signatures/templates/signatures/consent/create_step3_recipients.html`
  - `signatures/templates/signatures/consent/detail.html`
  - `signatures/templates/signatures/consent/verify.html`
  - `signatures/templates/signatures/consent/sign.html`
  - `signatures/templates/signatures/consent/complete.html`

### F. 기타

- 의존성 추가: `requirements.txt`
  - `pypdf`
  - `reportlab`
- 관리 편의용 admin 등록:
  - `SignatureRequestAdmin`, `SignatureRecipientAdmin`, `SignatureDocumentAdmin`
- 신규 메뉴용 데이터 마이그레이션:
  - `products/migrations/0034_add_parent_consent_product.py`

---

## 3) 테스트/검증

- 실행 완료:
  - `python manage.py check`
  - `python manage.py test signatures.tests_consent`
- 결과:
  - 모두 통과

---

## 4) 현재 동작 경로

- 교사용 대시보드: `/signatures/consent/`
- 생성 1단계: `/signatures/consent/create/step1/`
- 생성 2단계: `/signatures/consent/<request_id>/setup/`
- 생성 3단계: `/signatures/consent/<request_id>/recipients/`
- 상세/발송/다운로드:
  - `/signatures/consent/<request_id>/`
  - `/signatures/consent/<request_id>/preview/`
  - `/signatures/consent/<request_id>/send/`
  - `/signatures/consent/<request_id>/download/merged/`

---

## 5) 다음 작업 권장

1. Step2 실제 브라우저 QA
- PDF A4/Letter/다페이지 문서
- 이미지(PNG/JPG) 문서
- 모바일 터치 드래그/리사이즈

2. 좌표 정밀도 보강
- 최소/최대 박스 크기 정책
- 화면 배율 변경 시 박스 렌더 검증

3. 성능/안정성
- 대량 수신자, 대용량 PDF에서 통합 생성 시간 측정
- 타임아웃/예외 처리 가드 보완

4. 정책 문구/운영 문서
- 법적고지 텍스트 확정본 반영
- 보유기간/파기 정책 문구 확정

---

## 6) 참고 (작업 트리 상태)

- 이번 작업 중 `products/*` 일부 파일은 기존 병행 변경이 함께 보였고, 임의 수정/되돌림 없이 보존함.
- `.pytest_cache` 접근 경고는 sandbox 권한 이슈로 기능 영향 없음.

