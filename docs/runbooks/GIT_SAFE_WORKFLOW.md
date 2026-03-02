# Git Safe Workflow

이 문서는 `eduitit` 저장소를 안전하게 운영하기 위한 고정 절차다.
목표는 "서비스 섞임 방지", "빠른 복구", "예측 가능한 배포"다.

## 1) 브랜치 원칙

1. `main`
- 기존 서비스(artclass/core/seed_quiz/signatures 등) 개발과 배포는 기본적으로 여기서 진행한다.

2. `feature/sheetbook`
- `sheetbook` 관련 작업 전용 브랜치로 사용한다.
- `sheetbook`과 무관한 파일 변경은 커밋 대상에서 제외한다.

3. `spike/*`
- 실험/프로토타입 전용 브랜치.
- 검증 전에는 `main`, `feature/sheetbook`으로 직접 반영하지 않는다.

## 2) 작업 시작 전 30초 체크

아래 3개를 항상 먼저 실행한다.

```bash
git branch --show-current
git status --short
git log --oneline -n 3
```

## 3) 시나리오별 표준 절차

### A. Sheetbook 개발

```bash
git checkout feature/sheetbook
git pull
```

작업 후:

```bash
# 커밋 전 수동 가드 점검
python scripts/branch_path_guard.py --branch feature/sheetbook --staged

git add <sheetbook 관련 파일>
git commit -m "..."
git push origin feature/sheetbook
```

### B. 기존 서비스 고도화 (Sheetbook 아님)

```bash
git checkout main
git pull
```

작업 후:

```bash
git add <해당 서비스 파일만>
git commit -m "..."
git push origin main
```

### C. Sheetbook -> Main 반영

권장 방식은 통합 merge보다 선별 cherry-pick이다.

```bash
git checkout main
git pull
git checkout -b release/sheetbook-YYYYMMDD
git cherry-pick <sheetbook 커밋들>
```

검증 후:

```bash
git checkout main
git merge --ff-only release/sheetbook-YYYYMMDD
git push origin main
```

### D. 급한 핫픽스

```bash
git checkout main
git pull
git add <핫픽스 파일만>
git commit -m "fix: ..."
git push origin main
```

핫픽스는 작은 커밋 1개로 끝내는 것을 원칙으로 한다.

### E. 롤백

기본 롤백은 `revert`를 사용한다.

```bash
git revert <commit>
git push origin <branch>
```

`reset --hard`는 특별 승인 없이는 사용하지 않는다.

## 4) 백업 안전장치

불안한 작업(히스토리 재정리, 강제푸시) 전에 반드시 백업 브랜치를 만든다.

```bash
git branch backup/<name>-YYYYMMDD
```

예:

```bash
git branch backup/feature-sheetbook-before-clean-20260302
```

## 5) 문제 발생 시 복구 순서

1. `git branch --show-current`로 현재 브랜치 확인
2. `git status --short`로 미커밋 변경 확인
3. 미커밋 변경 임시 보관

```bash
git stash push -u -m "temp-recovery"
```

4. 백업 브랜치 또는 정상 커밋으로 복귀
5. 필요 시 stash 복원

```bash
git stash list
git stash apply "stash@{0}"
```

## 6) AI 에이전트에게 지시 템플릿

아래 문장을 그대로 사용해도 된다.

1. Sheetbook 작업 지시
- `feature/sheetbook에서 sheetbook 관련 파일만 수정해. 커밋 전 가드 검사하고 위반 파일이 있으면 멈추고 보고해.`

2. 기존 서비스 작업 지시
- `main에서 artclass만 수정해. sheetbook 파일이 섞이면 제외하고 진행해.`

3. 병합 지시
- `feature/sheetbook의 커밋 중 sheetbook 관련만 선별해서 main에 옮겨. 시작 전에 backup 브랜치 만들고 진행해.`

4. 안전모드 지시
- `작업 전에 현재 브랜치, 변경 파일, 대상 커밋을 먼저 요약하고 승인받은 뒤 진행해.`

## 7) 금지/주의

1. `feature/sheetbook`에서 `artclass/core/config` 변경 커밋 금지
2. `main`에서 대규모 실험 작업 금지
3. 백업 없이 `--force` 계열 명령 실행 금지
4. 같은 작업을 서로 다른 브랜치에서 동시에 장시간 진행 금지

## 8) 빠른 체크 명령 모음

```bash
# 현재 브랜치
git branch --show-current

# 커밋 직전 변경 요약
git status --short

# 최근 커밋
git log --oneline -n 5

# sheetbook 브랜치 가드 수동 점검
python scripts/branch_path_guard.py --branch feature/sheetbook --staged
```
