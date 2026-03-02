# HANDOFF: Sheetbook Branch Working Snapshot (latest)
Status: Working branch handoff (daily update)

작성일: 2026-03-02
대상 저장소: `eduitit`
대상 브랜치: `feature/sheetbook`
기준 브랜치: `main`

## 1) 브랜치 스냅샷

- current branch: `feature/sheetbook`
- tracking: `origin/feature/sheetbook`
- latest backup commit: `9ebde0f` (`wip(sheetbook): checkpoint backup 2`)
- main head reference: `90c8cd3`

작업 트리(작성 시점):
- modified: `artclass/templates/artclass/setup.html`
- modified: `sheetbook/management/commands/check_sheetbook_preflight.py`
- modified: `sheetbook/tests.py`
- untracked: `sheetbook/management/commands/check_sheetbook_consent_freeze.py`

## 2) 진행/결정 로그 (짧게 계속 누적)

- 2026-03-02: `feature/sheetbook` 브랜치 생성 및 원격 추적 연결 완료
- 2026-03-02: WIP 백업 커밋 2회(`49de938`, `9ebde0f`) + 원격 push 완료
- 2026-03-02: `main` 미머지 상태 유지(운영 반영 없음)

## 3) 중간 백업 규칙 (항상 반복)

1. 변경 저장
   - `git add -A`
   - `git commit -m "wip(sheetbook): <짧은 설명>"`
2. 원격 백업
   - `git push`
3. 기록 갱신
   - 본 문서의 `브랜치 스냅샷`/`진행 로그` 갱신

## 4) main 머지 전 필수 게이트

아래가 모두 통과되어야 `main` 머지 가능:

- `python manage.py check`
- `python manage.py test`
- `python manage.py test sheetbook.tests`
- `python manage.py makemigrations --check --dry-run`
- `python manage.py migrate --plan`

실행 결과 기록:
- gate run date:
- result summary:
- blocker:

## 5) 최종 반영 절차 (마지막 1회만)

1. `git switch main`
2. `git pull origin main`
3. `git merge --no-ff feature/sheetbook`
4. `git push origin main`
5. 배포 후 최소 스모크 점검

## 6) 장애 시 즉시 복구 절차

1. 기능 플래그 OFF(있으면 최우선)
2. `main`에서 머지 커밋 revert:
   - `git switch main`
   - `git log --oneline --graph -n 20`
   - `git revert -m 1 <merge_commit_sha>`
   - `git push origin main`
3. DB 이슈면 배포 전 스냅샷 기준 복구

## 7) 작성 규칙

- 이 문서는 `feature/sheetbook`의 "현재 작업 상태"만 기록
- 릴리즈 최종 판정은 `docs/handoff/sheetbook_release_decision_latest.json` 기준 사용
- 긴 설명 대신 "현재 상태 + 다음 행동 + 위험"만 짧게 업데이트
