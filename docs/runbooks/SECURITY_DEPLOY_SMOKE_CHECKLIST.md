# Security Deploy Smoke Checklist

## Goal
- 공개 표면에서 내부 힌트와 잔여 테스트 진입이 다시 노출되지 않는지 확인한다.
- 교사용 메인 업무 화면 사용성은 유지하면서, 공개 입력/공유 표면만 의도대로 보호되는지 확인한다.

## Pre-deploy checks
1. `python manage.py check`
2. `python manage.py test core.tests.test_ui_auth core.tests.test_auth_security_logging core.tests.test_seo_foundation artclass.tests qrgen.tests`
3. 변경된 JS가 있으면 `node --check <changed.js>`

## Production smoke
1. 로그인 화면에 `관리자 접속`, `bot_login_input`, `bot_password_input`, `bot_login_submit`가 없다.
2. `/robots.txt`에 `/secret-admin-kakio/`, `/accounts/`, `*/create/`, `*/edit/`, `*/review/`, `*/delete/` 같은 내부 힌트가 없다.
3. `/sitemap.xml`에 민감 서비스 상세와 민감 매뉴얼 상세가 포함되지 않는다.
4. `artclass` 설정 화면에서:
   - 유튜브가 아닌 URL은 저장되지 않는다.
   - 단계 이미지로 비이미지 파일 업로드 시 거절된다.
   - AI 붙여넣기 주의 문구가 보인다.
5. `qrgen` 화면에서 localhost/사설 IP 주소는 QR 생성이 거절된다.
6. `classcalendar`, `reservations`, `timetable` 메인 화면은 재로그인 증가 없이 기존처럼 열린다.
7. 학급 선택 API(`set_active_classroom`)가 정상 동작한다.
8. 관리자 로그인 성공/실패가 `core.auth_security` 로그에 남는다.

## Operational follow-ups
1. 운영 환경에서 staff/superuser 계정 MFA 등록 상태를 직접 점검한다.
2. robots/sitemap를 CDN 또는 별도 SEO 자산이 덮어쓰지 않는지 배포 후 재확인한다.
3. 공개 입력 도구 rate limit 차단 로그가 과도하지 않은지 첫 24시간 모니터링한다.
