# 세션 핸드오프 — 운영 진단 코드 레벨 보완

## 완료된 작업
- **계획서 저장**: `eduitit/docs/operational_fixes_plan.md`에 4개 항목 계획서 저장
- **항목 6 일부**: `cleanup_collect.py`의 stage 2 루프에 try/except 적용 완료

## 미완료 작업 (4개 항목 중 대부분 남음)

### 항목 6 (Cron) — 2/3 남음
- [ ] `version_manager/management/commands/delete_expired_versions.py` — `@transaction.atomic` 제거, logging 추가, per-item try/except
- [ ] `fortune/management/commands/cleanup_old_sessions.py` — sys/logging import, try/except + sys.exit(1)

### 항목 5 (RequestID) — 전체 미착수
- [ ] `core/middleware.py`에 `RequestIDMiddleware` + `RequestIDFilter` 추가
- [ ] `config/settings.py` LOGGING + MIDDLEWARE 업데이트
- [ ] `config/settings_production.py` LOGGING + MIDDLEWARE 업데이트

### 항목 4 (이미지 최적화) — 전체 미착수
- [ ] 8파일 12곳에 `loading="lazy"` 추가
- [ ] 4파일에 `|optimize` 필터 + `{% load cloudinary_extras %}` 추가

### 항목 2 (A11y) — 전체 미착수
- [ ] 3건 missing alt 수정
- [ ] 6파일 13곳 outline-none에 focus 스타일 추가
- [ ] ~25건 text-gray-400 → text-gray-500
- [ ] `core/management/commands/check_a11y.py` 신규 생성

## 검증 (마지막에)
```bash
cd /c/Users/kakio/eduitit && python manage.py check
python manage.py check_a11y
```

## 참고 파일
- 계획서: `eduitit/docs/operational_fixes_plan.md`
- 이전 세션 트랜스크립트: `C:\Users\kakio\.claude\projects\C--Users-kakio\2e04fd06-646a-47b7-847f-ce2824500afd.jsonl`
