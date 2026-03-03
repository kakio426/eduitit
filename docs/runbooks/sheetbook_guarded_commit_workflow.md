# Sheetbook Guarded Commit Workflow

목적: `feature/sheetbook`에서 커밋 전에 경로 가드를 강제해 브랜치 분리 위반을 줄인다.

## 1) 기본 사용

1. 변경 파일 스테이징
   - `git add <sheetbook-allowed-paths...>`
2. 가드만 먼저 점검
   - `python scripts/run_sheetbook_guarded_commit.py --guard-only`
3. 커밋 실행
   - `python scripts/run_sheetbook_guarded_commit.py -m "feat(sheetbook): <summary>"`

## 2) 커밋 + 푸시 한 번에

- `python scripts/run_sheetbook_guarded_commit.py -m "chore(sheetbook): <summary>" --push`

## 3) 동작 원리

- 내부에서 `python scripts/branch_path_guard.py --branch feature/sheetbook --staged` 실행
- 가드 실패 시 커밋/푸시를 중단
- 기본적으로 현재 브랜치가 `feature/sheetbook`이 아니면 실행 차단

## 4) 자주 보는 실패 케이스

- `no staged files to commit`
  - 스테이징 누락. `git add` 후 재실행.
- `blocked: current branch ... != expected feature/sheetbook`
  - 브랜치 전환 후 재실행 또는 `--branch`/`--expected-branch` 옵션 확인.
- `branch-guard blocked`
  - 스테이징 파일 중 비허용 경로 포함. `git reset <file>`로 제외 후 재실행.
