# Seed Quiz 최종 계획서 (구현 착수용, Phase 1)

기준 프로젝트: `C:\Users\kakio\eduitit`  
목표: 교사 원클릭 생성 + 교사 QA 승인 + 학생 태블릿 5분 풀이 + happy_seed 보상 연동  
운영 기준일: 2026-02-21

## 1. 결정사항 잠금 (변경 금지)
1. `seed_quiz`는 독립 앱으로 구현한다. `happy_seed`/`consent` 코어 로직은 직접 수정하지 않는다.
2. 보상은 오직 `happy_seed.services.engine.add_seeds()` 또는 `grant_tickets()`로 지급한다.
3. 학생 제출/보상은 멱등성과 트랜잭션을 강제한다.
4. AI 생성 실패 시 즉시 폴백 문제은행으로 전환한다.
5. 교사 승인(`publish`) 전에는 학생에게 절대 노출하지 않는다.
6. 태블릿 UX는 "확대 금지, 큰 터치 영역, 한 화면 한 행동" 원칙을 따른다.

## 2. 범위 (Phase 1)
1. 교사 대시보드에서 프리셋 퀴즈 생성.
2. AI 결과 검증 및 폴백 자동 전환.
3. 교사 QA 미리보기 후 배포 승인.
4. 학생 게이트 진입 및 3문항 풀이.
5. 최종 제출/채점/보상 지급.
6. 교사 진행 현황 HTMX 갱신.
7. 제품 등록/매뉴얼/배포 체인 통합.
8. 단위+통합 테스트 및 태블릿 수동 QA.

## 3. 비범위 (Phase 1에서 제외)
1. 자동 새벽 생성(스케줄러 기반).
2. 모둠 퀘스트형 완전 게임화 UI.
3. 문항 편집기(교사가 직접 문제 수정).
4. 학부모 알림 자동 발송.

## 4. 파일 구조 계획
1. 앱 생성: `seed_quiz/`
2. 모델: `seed_quiz/models.py`
3. 폼: `seed_quiz/forms.py`
4. 뷰: `seed_quiz/views.py`
5. 라우팅: `seed_quiz/urls.py`
6. 서비스: `seed_quiz/services/generation.py`, `seed_quiz/services/validator.py`, `seed_quiz/services/grading.py`, `seed_quiz/services/gate.py`
7. 템플릿: `seed_quiz/templates/seed_quiz/teacher_dashboard.html`, `seed_quiz/templates/seed_quiz/student_gate.html`, `seed_quiz/templates/seed_quiz/student_play.html`, `seed_quiz/templates/seed_quiz/partials/*.html`
8. 정적: `seed_quiz/static/seed_quiz/css/student.css`, `seed_quiz/static/seed_quiz/js/student.js`
9. 데이터: `seed_quiz/data/fallback_quizzes_v1.json`
10. 어드민: `seed_quiz/admin.py`
11. 테스트: `seed_quiz/tests/test_models.py`, `seed_quiz/tests/test_validator.py`, `seed_quiz/tests/test_generation.py`, `seed_quiz/tests/test_grading.py`, `seed_quiz/tests/test_teacher_flow.py`, `seed_quiz/tests/test_student_flow.py`
12. 설정 연결: `config/settings.py`, `config/settings_production.py`, `config/urls.py`
13. 제품 등록: `products/management/commands/ensure_seed_quiz.py`
14. 런타임 체인: `core/management/commands/bootstrap_runtime.py`

## 5. 데이터 모델 상세 설계 (`seed_quiz/models.py`)
1. `SQQuizSet`
2. 필드: `id(UUID PK)`, `classroom(FK HSClassroom)`, `target_date(Date)`, `preset_type(Char)`, `grade(Int)`, `title(Char)`, `status(draft/published/closed/failed)`, `source(ai/fallback)`, `is_fallback(Bool)`, `time_limit_seconds(Int default=600)`, `created_by(FK User)`, `published_by(FK User nullable)`, `published_at`, `created_at`, `updated_at`
3. 인덱스: `(classroom, target_date, status)`, `(status, published_at)`
4. 제약: 같은 반/같은 날짜/같은 프리셋에서 `published`는 1개만 허용(조건부 UniqueConstraint)

5. `SQQuizItem`
6. 필드: `id(UUID PK)`, `quiz_set(FK)`, `order_no(1~3)`, `question_text(Text)`, `choices(JSONField list[str])`, `correct_index(Int 0~3)`, `explanation(Text blank)`, `difficulty(Char)`, `created_at`
7. 인덱스/제약: `Unique(quiz_set, order_no)`, `Check(correct_index between 0 and 3)`
8. `clean()` 강제: choices 길이=4, 공백/중복 없음, 깨진 문자(`�`) 금지

9. `SQAttempt`
10. 필드: `id(UUID PK)`, `quiz_set(FK)`, `student(FK HSStudent)`, `status(in_progress/submitted/rewarded)`, `request_id(UUID unique)`, `score(Int)`, `max_score(Int)`, `reward_seed_amount(Int)`, `reward_applied_at`, `consent_snapshot(Char)`, `started_at`, `submitted_at`, `updated_at`
11. 제약: `Unique(student, quiz_set)` (1세트 1시도)

12. `SQAttemptAnswer`
13. 필드: `id(UUID PK)`, `attempt(FK)`, `item(FK)`, `selected_index(Int 0~3)`, `is_correct(Bool)`, `answered_at`
14. 제약: `Unique(attempt, item)`

15. `SQGenerationLog`
16. 필드: `id(UUID PK)`, `quiz_set(FK nullable)`, `level(info/warn/error)`, `code(Char)`, `message(Text)`, `payload(JSON)`, `created_at`
17. 목적: AI 실패/검증 실패/폴백 기록 추적

## 6. 상태 머신 설계
1. `SQQuizSet`: `draft -> published -> closed`, `draft -> failed`
2. `SQAttempt`: `in_progress -> submitted -> rewarded`, `in_progress -> submitted`
3. 전이 규칙: `published` 세트가 생기면 기존 같은 조건 세트는 `closed`로 전환
4. 전이 규칙: `rewarded`는 만점+동의승인+보상 성공시에만

## 7. URL 설계 (`seed_quiz/urls.py`)
1. `GET /seed-quiz/`: 랜딩
2. `GET /seed-quiz/class/<uuid:classroom_id>/dashboard/`: 교사용 대시보드
3. `POST /seed-quiz/class/<uuid:classroom_id>/htmx/generate/`: 생성
4. `POST /seed-quiz/class/<uuid:classroom_id>/htmx/publish/<uuid:set_id>/`: 배포 승인
5. `GET /seed-quiz/class/<uuid:classroom_id>/htmx/progress/`: 진행 현황 partial
6. `GET /seed-quiz/gate/<slug:class_slug>/`: 학생 진입 게이트
7. `POST /seed-quiz/gate/<slug:class_slug>/start/`: 학생 시작/시도 생성
8. `GET /seed-quiz/play/`: 학생 플레이 셸
9. `GET /seed-quiz/htmx/play/current/`: 현재 문항 partial
10. `POST /seed-quiz/htmx/play/answer/`: 한 문항 제출/다음 문항
11. `POST /seed-quiz/htmx/play/finish/`: 최종 제출/채점/보상
12. `GET /seed-quiz/htmx/play/result/`: 결과 partial

## 8. 권한/접근 제어
1. 교사 경로는 `login_required` + `classroom.teacher == request.user` 강제
2. 학생 경로는 비로그인 허용
3. 학생은 `class_slug + (번호+이름)`로 식별 후 서버 세션에 고정
4. 세션키: `sq_classroom_id`, `sq_student_id`, `sq_quiz_set_id`, `sq_attempt_id`, `sq_request_id`
5. 모든 학생 액션은 세션값과 DB를 교차검증
6. URL 파라미터로 `student_id` 직접 받지 않음(변조 차단)

## 9. AI 생성 및 폴백 설계 (`seed_quiz/services/generation.py`)
1. 입력: `classroom`, `preset_type`, `grade`, `target_date`, `created_by`
2. 동작: AI 생성 시도 -> 구조/품질 검증 -> 실패 시 폴백 로드
3. 타임아웃: 4~6초
4. 재시도: 1회만
5. 실패 기준: 타임아웃, JSON 파싱 실패, 검증 실패
6. 폴백: `seed_quiz/data/fallback_quizzes_v1.json`에서 프리셋/학년 매칭 랜덤 선택
7. 저장: 항상 `draft`로 생성하고 교사 QA 화면 반환
8. 로그: `SQGenerationLog`에 단계별 코드 기록

## 10. 문제 검증 설계 (`seed_quiz/services/validator.py`)
1. 문항 수 정확히 3개
2. 각 문항 질문 비어있지 않음
3. 선택지 정확히 4개
4. 선택지 공백 금지
5. 선택지 중복 금지
6. `correct_index in [0,1,2,3]`
7. 한글 깨짐 문자(`�`) 포함 금지
8. 제어문자/HTML 태그 제거
9. 금칙어(폭력/혐오/성인/정치편향) 필터
10. 길이 제한: 질문 120자, 선택지 40자, 해설 200자
11. NFC 정규화 후 저장

## 11. 교사 플로우 상세 (`seed_quiz/views.py`)
1. 대시보드 진입 시 오늘 `draft/published` 세트와 최근 결과 표시
2. `generate` 클릭 시 HTMX 요청
3. 서버는 생성 후 `teacher_preview` partial 반환
4. 교사는 정답/해설 포함 미리보기 확인
5. 이상하면 "다시 생성"
6. 정상이면 `publish` 클릭
7. publish 시 해당 반/날짜/프리셋 기존 published는 close
8. 성공 메시지와 학생 접속 URL/QR 표시
9. 진행현황 partial은 15초 polling
10. 표시 항목: 총원, 시작자, 제출자, 만점자, 미제출자

## 12. 학생 플로우 상세
1. `gate`에서 오늘 published 세트 존재 확인
2. 없으면 "아직 배포 전" 대기 카드 + 자동 새로고침
3. 있으면 학생 번호+이름 입력
4. 서버 매칭 성공 시 `SQAttempt` 생성 또는 재개
5. 이미 제출 완료 시 결과 화면으로 직행
6. 플레이 셸 로딩 후 `current` partial 자동 호출
7. 선택지 탭 -> `answer` POST
8. 서버가 저장 후 다음 문항 partial 반환
9. 마지막 문항이면 `finish` 수행
10. 결과 화면에서 점수/보상/동의상태 안내 분리 표시

## 13. 보상 트랜잭션 설계 (`seed_quiz/services/grading.py`)
1. `@transaction.atomic`
2. `SQAttempt.select_for_update()`
3. 이미 `submitted/rewarded`면 즉시 기존 결과 반환(멱등)
4. `request_id` 일치 검증
5. 점수 계산 및 `submitted` 저장
6. 동의 스냅샷 확인
7. 만점+동의승인 시 `add_seeds()` 호출
8. `add_seeds` 파라미터: `reason='behavior'`, `detail='오늘의 씨앗 퀴즈 만점'`, `request_id=uuid.uuid5(...)`
9. 성공 시 `rewarded` 전환
10. `HSClassEventLog` 기록

## 14. HTMX/프론트엔드 규격
1. 학생 페이지에만 `viewport` 확장 블록으로 `user-scalable=no` 적용
2. 터치 요소 최소 높이 `60px`
3. 본문 텍스트 최소 `text-xl`, 선택지는 `text-lg~xl`
4. 컨테이너 `max-w-screen-md mx-auto`
5. 문제 영역 `min-h-[100dvh]`, `overflow-y-auto`
6. 선택지 영역 하단 고정(세로 스크롤 시도 방지)
7. 로딩 오버레이는 기본 숨김, `.htmx-request` 시만 노출
8. 통신 중 버튼 disabled 처리
9. `noscript` 폴백 폼 유지
10. 글꼴 스택은 다중 fallback 지정
11. 비율 깨짐 방지로 `vw` 타이포 금지
12. 이미지 없이 텍스트 중심 카드형 UI

## 15. 오류 처리/메시지 규격
1. 교사 생성 실패: "AI 문제 생성 실패, 기본 문제로 전환 시도"
2. 폴백 실패: "문제 데이터 점검 필요" + 로그 코드 표시
3. 학생 매칭 실패: "번호/이름을 다시 확인"
4. 제출 중복: 조용히 기존 결과 반환
5. 동의 미완료: "학습은 완료, 보상은 동의 후 지급"
6. 서버 예외: 사용자 메시지 일반화, 내부 상세는 로그만
7. 모든 에러 메시지는 한글 고정 문구로 통일

## 16. 로그/관측성
1. logger 이름: `seed_quiz.*`
2. 모든 주요 이벤트에 `request_id`, `classroom_id`, `quiz_set_id`, `attempt_id` 포함
3. 이벤트: 생성시도, 검증실패, 폴백전환, publish, 시작, 문항응답, 최종제출, 보상성공/실패
4. 경고 레벨: 검증 실패/폴백 전환
5. 에러 레벨: 생성/저장/보상 예외

## 17. 관리자(Admin) 설계
1. `SQQuizSet` list: 날짜, 반, 프리셋, 상태, source, created/published by
2. `SQQuizItem` inline 보기
3. `SQAttempt` list: 학생, 점수, 상태, 보상 여부
4. `SQGenerationLog` 읽기 전용

## 18. 제품/운영 통합
1. `ensure_seed_quiz.py` 생성
2. `Product` 등록: 제목, 아이콘, `launch_route_name`
3. `ProductFeature` 3개 이상
4. `ServiceManual` + `ManualSection` 3개 이상 생성
5. `bootstrap_runtime.py`에 `ensure_seed_quiz` 추가
6. `config/urls.py`에 `path('seed-quiz/', include(...))` 등록
7. `happy_seed/classroom_detail.html`에 교사 진입 버튼 추가

## 19. 테스트 계획 (자동)
1. 모델 검증 테스트
2. validator 테스트(정답누락/중복선택지/깨진문자/금칙어)
3. generation 테스트(AI 성공/실패->폴백)
4. grading 테스트(멱등/동의미완료/만점보상)
5. 교사 플로우 테스트(generate->preview->publish)
6. 학생 플로우 테스트(gate->start->3문항->finish)
7. HTMX 없는 폴백 테스트
8. 권한 테스트(타 교사 접근 차단)
9. happy_seed 연동 회귀 테스트

## 20. 테스트 계획 (수동 태블릿 QA)
1. iPad 세로/가로
2. 갤럭시 탭 세로/가로
3. 저해상도 안드로이드 태블릿
4. 확대/축소 방지 동작 확인
5. 빠른 연타/뒤로가기/재접속
6. 네트워크 느림/순단 상황
7. 문항 글자 길이 극단값 표시 확인
8. 동의 미완료 학생 결과 문구 확인

## 21. 성능 기준
1. 게이트/문항 응답 서버 처리 p95 < 300ms (DB 기준)
2. 생성 요청 AI 제외 서버 처리 p95 < 500ms
3. 폴백 전환 시 1초 내 preview 반환
4. HTMX partial payload 20KB 이하 유지

## 22. 개인정보/보안 기준
1. 학생 식별은 최소 정보(번호+이름)만 사용
2. attempt 데이터에 민감정보 저장 금지
3. CSRF 필수
4. teacher endpoint는 소유권 검증 필수
5. 공개 링크는 클래스 slug 기반이되 내부 액션은 세션 검증

## 23. 마이그레이션/실행 커맨드
1. `python manage.py makemigrations seed_quiz`
2. `python manage.py migrate`
3. `python manage.py ensure_seed_quiz`
4. `python manage.py check`
5. `python manage.py test seed_quiz happy_seed.tests`
6. `node --check seed_quiz/static/seed_quiz/js/student.js`

## 24. 배포 순서
1. 코드 배포(기능 노출 전)
2. 내부 교사 파일럿 반 1개 publish
3. 3일 안정화 로그 확인
4. 전반 확대
5. 이상 시 set 상태 `closed`로 즉시 차단

## 25. 롤백 계획
1. `Product.is_active=False`로 노출 즉시 중지
2. `seed_quiz` URL 유지, gate는 점검 화면 반환
3. 보상 중단 플래그 활성화(서비스 레벨)
4. 원인 분석 후 재오픈

## 26. 완료 정의 (DoD)
1. 교사 원클릭 생성/QA/배포 완료
2. 학생 태블릿에서 깨짐 없이 3문항 풀이 가능
3. 정답 누락/문항 비정상 데이터 학생 노출 0건
4. AI 실패 시 폴백 100% 동작
5. 중복 제출 시 보상 중복 0건
6. 동의 미완료 보상 차단 정확
7. 자동/수동 QA 체크리스트 전부 통과
8. 운영 문서/매뉴얼/제품 등록 완료

