# Handoff: consent 분리 및 안정화 (2026-02-18)

## 1. 요약
- `consent`는 별도 서비스로 분리 운영 중이며, 대시보드 진입/라우팅/제품 연결이 독립 경로로 동작함.
- `consent` UI는 `collect/signatures`와 동일 계열(클레이모피즘 톤)로 정렬함.
- `consent` 한글 깨짐 이슈를 템플릿/폼/뷰 중심으로 복구함.
- 테스트 기준으로 `consent`, `collect`, `signatures` 회귀 이상 없음.

## 2. 이번 턴 실제 반영 내용
- 한글 복구 및 UI 정리
  - `consent/forms.py`
  - `consent/views.py`
  - `consent/templates/consent/create.html`
  - `consent/templates/consent/create_step1.html`
  - `consent/templates/consent/create_step2_positions.html`
  - `consent/templates/consent/create_step3_recipients.html`
  - `consent/templates/consent/dashboard.html`
  - `consent/templates/consent/detail.html`
  - `consent/templates/consent/verify.html`
  - `consent/templates/consent/sign.html`
  - `consent/templates/consent/complete.html`
- 기본 법적 고지 UX
  - 법적 고지 입력은 선택으로 안내
  - 비워두면 서버 기본 문구 자동 적용

## 3. 분리 상태 점검 결과
- 독립 라우팅
  - `config/urls.py`에 `path('consent/', include('consent.urls', namespace='consent'))` 존재
- 대시보드 런치 분기
  - `products/templates/products/partials/preview_modal.html`에서
  - `"동의서는 나에게 맡겨" -> consent:dashboard` 연결 확인
- 런타임 부트스트랩
  - `core/management/commands/bootstrap_runtime.py`에 `ensure_consent` 등록 확인
- 제품 보장 커맨드
  - `products/management/commands/ensure_consent.py` 존재

## 4. 검증 결과
- 정적 점검
  - `python manage.py check` 통과
- 테스트
  - `python manage.py test consent -v 2` 통과 (4 tests)
  - `python manage.py test collect.tests.test_collect_flow -v 2` 통과 (2 tests)
  - `python manage.py test signatures -v 2` 통과 (1 test)
- 좌표 정확성
  - 위치설정 JS 비율 저장식과 PDF 합성식(`resolve_position`)의 좌표 변환 일치 확인
  - 비율 round-trip 스크립트 검증 `True`

## 5. 확인된 잔여 이슈 (중요)
- `consent/services.py` 내부에 깨진 한글 문자열이 남아 있을 가능성 있음
  - 대상: 워터마크/미리보기 라벨/비동의 사유 요약 텍스트
  - 기능은 동작하지만 출력 문구 품질 이슈 가능
- 완전 분리 관점에서 모델 결합이 남아 있음
  - `consent/models.py`가 `signatures.consent_models`를 re-export 중
  - 즉, UI/라우팅/제품은 분리됐지만 모델 소스는 아직 `signatures`에 의존

## 6. 다음 작업 권장 순서
1. `consent/services.py` 한글 문자열 정리(UTF-8 고정)
2. `consent` 모델 완전 이관
   - `signatures.consent_models` 의존 제거
   - 마이그레이션 충돌 없이 테이블 유지 전략 적용
3. 재검증
   - `python manage.py check`
   - `python manage.py test consent collect.tests.test_collect_flow signatures -v 2`

## 7. Git 기록
- 반영 커밋: `770e891`
- 메시지: `fix(consent): restore korean text and align clay UI`
- 원격 반영: `main` push 완료
