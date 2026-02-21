# 우리반BTI `이름 -> 별명` 전환 작업 계획

## 범위 선언
- target_app: `studentmbti`
- do_not_touch_apps: `ssambti`, `consent`, `reservations`, `products`, `core` (단순 링크/타이틀 문구 제외)

## 목표
- 학생 입력 문구를 `이름`에서 `별명`으로 전환
- 저장 필드(`student_name`)는 당장 유지해서 DB 마이그레이션 없이 호환성 확보
- UI/검증/CSV/로그 문구만 일관되게 변경

## 변경 파일 후보
- `studentmbti/templates/studentmbti/test.html`
- `studentmbti/views.py`
- `studentmbti/templates/studentmbti/result.html`
- `studentmbti/templates/studentmbti/session_detail.html`
- `studentmbti/templates/studentmbti/partials/results_list.html`
- `studentmbti/templates/studentmbti/partials/fullscreen_results.html`
- `studentmbti/tests.py`

## 단계별 실행
1. UI 문구 전환
- `test.html`의 입력 안내/placeholder/step 텍스트를 `별명` 기준으로 변경
- 예: `이름 입력` -> `별명 입력`, `이름이 뭐야?` -> `별명이 뭐야?`

2. 서버 검증 메시지 전환
- `views.py`의 에러 메시지:
- `이름을 입력해주세요.` -> `별명을 입력해주세요.`
- 내부 변수명/DB 필드명(`student_name`)은 그대로 유지

3. 결과/목록 화면 라벨 정리
- 교사용 결과 화면과 리스트 라벨을 `학생 이름` -> `별명`
- CSV 헤더도 `학생 이름` -> `별명`으로 변경 여부 결정
- 추천: CSV 헤더도 `별명`으로 통일

4. 접근성/입력 정책 보강(권장)
- 최대 길이 명시(예: 12~20자)
- 공백-only 차단
- 금칙어/개인정보(전화번호 형태 등) 간단 필터 고려

5. 테스트 반영
- `studentmbti/tests.py`에서 메시지/폼 입력 관련 기대값을 `별명` 기준으로 수정
- 핵심 테스트:
- 세션 입장 -> 별명 입력 -> 분석 완료
- 공백 입력 시 400 + `별명을 입력해주세요.`

## 회귀 체크리스트
- 모바일에서 별명 입력 단계 정상 노출
- 입력 후 결과 페이지 진입 정상
- 교사 대시보드 결과 목록 정상
- CSV 다운로드 컬럼명/값 정상

## 커밋 단위 추천
1. `[feat] 우리반BTI 입력 문구를 별명 기준으로 전환`
2. `[test] 우리반BTI 별명 입력 플로우 테스트 갱신`

## 보류(이번 작업에서 제외)
- 모델 필드명 `student_name` -> `nickname` 마이그레이션
- 관리자(admin) 컬럼명 변경
- 과거 데이터 일괄 변환

## 작업 후 검증 명령
```bash
python manage.py check
python manage.py test studentmbti -v 2
```
