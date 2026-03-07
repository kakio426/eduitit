# QA: Docviewer Teacher Journey (2026-03-07)

대상:
- `docviewer`
- URL: `/docviewer/`

검증 환경:
- 로컬 Django runserver (`127.0.0.1:8016`)
- 관리자 로그인 경로: `/secret-admin-kakio/login/?next=/docviewer/`
- 헤드리스 브라우저: Playwright Chromium
- 테스트 PDF: reportlab로 생성한 2페이지 샘플 PDF

## 와이어프레임 체크
- 좌측에 `교사 작업 흐름` 3단계가 고정 노출됨
- 좌측에 `PDF 파일 선택`, `다른 PDF 고르기`, `인쇄하기 (새 탭)`이 즉시 보임
- 우측에 `미리보기 화면`, `현재 위치`, `확대 비율`, `다음 행동`이 동시에 보임
- 첫 진입 기본 상태는 `0 / 0쪽`, `100%`, `먼저 PDF를 선택해 주세요.`로 일관됨

## 스모크 결과
- 로그인 후 `/docviewer/` 진입: PASS
- PDF 업로드 후 첫 페이지 렌더: PASS
- 확대 버튼 클릭 후 `100% -> 120%`: PASS
- 다음 쪽 클릭 후 `2 / 2쪽`: PASS
- 이전 쪽 클릭 후 `1 / 2쪽`: PASS
- 인쇄하기 (새 탭) 클릭 후 성공 상태 문구 노출: PASS
- 브라우저 콘솔 `error`: 0건
- 페이지 런타임 에러: 0건

## 핵심 관찰값
- `page_indicator_before`: `0 / 0쪽`
- `page_indicator_after_next`: `2 / 2쪽`
- `page_indicator_after_prev`: `1 / 2쪽`
- `zoom_before`: `100%`
- `zoom_after`: `120%`
- `status_after_print`: `인쇄용 새 탭을 열었습니다. 브라우저 인쇄 기능을 사용해 주세요.`
- `page_summary`: `1쪽을 보고 있습니다. 총 2쪽입니다.`
- `next_step`: `다음 쪽 버튼으로 이어서 확인하거나 확대해서 자세히 보세요.`

## 메모
- 첫 구현은 브라우저 메모리 기반 PDF 미리보기만 포함합니다.
- 서버 저장, 공유 링크, 협업, 원격 PDF 프록시는 V1 범위에서 제외했습니다.
