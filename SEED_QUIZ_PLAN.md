# Seed Quiz (씨앗 퀴즈) 구현 최종 계획

## Context

`happy_seed` 교실 보상 시스템에 연결되는 독립 앱 `seed_quiz`를 신규 구현한다.
교사가 원클릭으로 AI 3문항 퀴즈를 생성 → QA 후 배포 → 학생이 태블릿으로 5분 내 풀이 → 만점+동의 시 씨앗 보상.

**두 계획서 비교 후 권장 방향:**
- 사용자 초기 계획 + SEED_QUIZ_FINAL_PLAN.md를 통합. 파일의 계획이 더 정밀하므로 기준으로 삼되, 초기 계획의 UX 코드 패턴(선택지 구조, grading 스켈레톤)을 흡수.
- **핵심 변경**: 3번째 문항 답변 시 즉시 채점+보상(별도 finish 버튼 없음) → 아이들 UX 간소화
- AI 모델: 기존 fortune 앱과 동일하게 DeepSeek (`MASTER_DEEPSEEK_API_KEY`), sync OpenAI 클라이언트 사용
- 보상 idempotency: `uuid.uuid5(NAMESPACE_URL, f"sq_reward:{attempt.id}")` (예측 가능, 절대 중복 없음)

---

## 0. 절대 불변 결정 (Implementation Locks)

1. `seed_quiz`는 독립 앱. `happy_seed`, `consent` 코어 로직 직접 수정 없음
2. 보상은 오직 `happy_seed.services.engine.add_seeds()` 호출로만 지급
3. `add_seeds()`에는 consent 체크가 없음 → grading.py에서 직접 체크 필수
4. AI 실패 → 즉시 `fallback_quizzes_v1.json` 전환
5. `published` 전 학생 노출 절대 없음
6. `user-scalable=no`는 student_play.html에만 격리 적용
7. bootstrap_runtime.py에 퀴즈 자동 생성 로직 절대 금지 (교사 액션만)

---

## 1. 파일 목록 (신규 생성 & 수정)

### 신규 생성
```
seed_quiz/
├── __init__.py
├── apps.py
├── models.py
├── admin.py
├── forms.py
├── views.py
├── urls.py
├── services/
│   ├── __init__.py
│   ├── validator.py
│   ├── generation.py
│   ├── grading.py
│   └── gate.py
├── templates/seed_quiz/
│   ├── teacher_dashboard.html
│   ├── student_gate.html
│   ├── student_play.html
│   └── partials/
│       ├── teacher_preview.html
│       ├── teacher_progress.html
│       ├── play_item.html
│       └── play_result.html
├── static/seed_quiz/css/
│   └── student.css
├── data/
│   └── fallback_quizzes_v1.json
└── tests/
    ├── __init__.py
    ├── test_models.py
    ├── test_validator.py
    ├── test_generation.py
    ├── test_grading.py
    ├── test_teacher_flow.py
    └── test_student_flow.py

products/management/commands/ensure_seed_quiz.py
```

### 수정 필요
| 파일 | 변경 내용 |
|------|-----------|
| `config/settings.py` | `INSTALLED_APPS`에 `'seed_quiz.apps.SeedQuizConfig'` 추가 |
| `config/settings_production.py` | 동일하게 동기화 |
| `config/urls.py` | `path('seed-quiz/', include('seed_quiz.urls', namespace='seed_quiz'))` 추가 |
| `core/management/commands/bootstrap_runtime.py` | steps에 `("ensure_seed_quiz", ...)` 추가 |
| `happy_seed/templates/happy_seed/classroom_detail.html` | Quick Actions 그리드에 "씨앗 퀴즈" 버튼 추가 |
| `products/templates/products/partials/preview_modal.html` | `{% elif product.title == '씨앗 퀴즈' %}{% url 'seed_quiz:landing' %}` 분기 추가 |

---

## 2. 데이터 모델 (`seed_quiz/models.py`)

### SQQuizSet
```python
class SQQuizSet(models.Model):
    STATUS = [('draft','초안'),('published','배포중'),('closed','종료'),('failed','생성실패')]
    SOURCE = [('ai','AI'),('fallback','기본문제')]
    PRESET_CHOICES = [
        ('general', '상식'),('math', '수학'),('korean', '국어'),
        ('science', '과학'),('social', '사회'),('english', '영어'),
    ]
    id = UUIDField(pk=True, default=uuid4)
    classroom = FK(HSClassroom, CASCADE, related_name='sq_quiz_sets')
    target_date = DateField()
    preset_type = CharField(max_length=20, choices=PRESET_CHOICES, default='general')
    grade = IntegerField(default=3)  # 1~6
    title = CharField(max_length=100)
    status = CharField(max_length=10, choices=STATUS, default='draft')
    source = CharField(max_length=10, choices=SOURCE, default='ai')
    time_limit_seconds = IntegerField(default=600)
    created_by = FK(User, SET_NULL, null=True)
    published_by = FK(User, SET_NULL, null=True, blank=True)
    published_at = DateTimeField(null=True, blank=True)
    created_at = auto, updated_at = auto

    class Meta:
        constraints = [UniqueConstraint(
            fields=['classroom','target_date','preset_type'],
            condition=Q(status='published'),
            name='unique_published_quiz_per_class_date_preset'
        )]
        indexes = [
            Index(fields=['classroom','target_date','status']),
            Index(fields=['status','published_at']),
        ]
```

### SQQuizItem
```python
class SQQuizItem(models.Model):
    id = UUIDField(pk=True)
    quiz_set = FK(SQQuizSet, CASCADE, related_name='items')
    order_no = IntegerField()  # 1,2,3
    question_text = TextField()
    choices = JSONField()  # list[str], 길이=4
    correct_index = IntegerField()  # 0~3
    explanation = TextField(blank=True)
    difficulty = CharField(max_length=10, default='medium')
    created_at = auto

    class Meta:
        unique_together = [('quiz_set','order_no')]
        constraints = [CheckConstraint(
            check=Q(correct_index__gte=0) & Q(correct_index__lte=3),
            name='sq_item_correct_index_range'
        )]
```

### SQAttempt
```python
class SQAttempt(models.Model):
    STATUS = [('in_progress','진행중'),('submitted','제출완료'),('rewarded','보상완료')]
    id = UUIDField(pk=True)
    quiz_set = FK(SQQuizSet, CASCADE, related_name='attempts')
    student = FK(HSStudent, CASCADE, related_name='sq_attempts')
    status = CharField(max_length=15, choices=STATUS, default='in_progress')
    request_id = UUIDField(unique=True, default=uuid4)
    score = IntegerField(default=0)
    max_score = IntegerField(default=3)
    reward_seed_amount = IntegerField(default=0)
    consent_snapshot = CharField(max_length=15, blank=True)
    reward_applied_at = DateTimeField(null=True, blank=True)
    started_at = auto_now_add
    submitted_at = DateTimeField(null=True, blank=True)
    updated_at = auto

    class Meta:
        unique_together = [('student','quiz_set')]
```

### SQAttemptAnswer
```python
class SQAttemptAnswer(models.Model):
    id = UUIDField(pk=True)
    attempt = FK(SQAttempt, CASCADE, related_name='answers')
    item = FK(SQQuizItem, CASCADE)
    selected_index = IntegerField()
    is_correct = BooleanField()
    answered_at = auto_now_add

    class Meta:
        unique_together = [('attempt','item')]
        constraints = [CheckConstraint(
            check=Q(selected_index__gte=0) & Q(selected_index__lte=3),
            name='sq_answer_selected_index_range'
        )]
```

### SQGenerationLog
```python
class SQGenerationLog(models.Model):
    LEVEL = [('info','정보'),('warn','경고'),('error','오류')]
    id = UUIDField(pk=True)
    quiz_set = FK(SQQuizSet, SET_NULL, null=True, blank=True)
    level = CharField(max_length=5, choices=LEVEL, default='info')
    code = CharField(max_length=50)
    message = TextField()
    payload = JSONField(default=dict, blank=True)
    created_at = auto_now_add
```

---

## 3. 서비스 레이어

### validator.py, generation.py, grading.py, gate.py
- 계획서 본문 참조 (상세 코드 포함)

---

## 4. URL 구조

```
''                                    → landing
class/<uuid>/dashboard/               → teacher_dashboard
class/<uuid>/htmx/generate/           → htmx_generate
class/<uuid>/htmx/publish/<uuid>/     → htmx_publish
class/<uuid>/htmx/progress/           → htmx_progress
gate/<slug>/                          → student_gate
gate/<slug>/start/                    → student_start
play/                                 → student_play_shell
htmx/play/current/                    → htmx_play_current
htmx/play/answer/                     → htmx_play_answer
htmx/play/result/                     → htmx_play_result
```

---

## 5. 보안 체크리스트

| 위협 | 방어 |
|------|------|
| 교사 URL 무단 접근 | `classroom.teacher == request.user` 검증 |
| 학생 URL 변조 | URL에 문항 ID 없음, 세션 기반 상태 |
| 다른 학생 답안 접근 | attempt_id를 세션에서만 읽음 |
| 중복 보상 | select_for_update + uuid5 request_id |
| 중복 퀴즈 생성 | DB UniqueConstraint (published) + get_or_create(draft) |
| XSS | choices/question 저장 시 HTML 태그 제거 |
| CSRF | 모든 POST에 csrf_token + HTMX 헤더 |

---

## 6. 구현 순서

1. Step 1: 앱 뼈대 (apps.py, models.py, admin.py)
2. Step 2: 마이그레이션
3. Step 3: fallback_quizzes_v1.json + fallback_loader.py
4. Step 4: validator.py, generation.py, grading.py, gate.py
5. Step 5: views.py + urls.py
6. Step 6: 템플릿 전체
7. Step 7: student.css
8. Step 8: ensure_seed_quiz.py
9. Step 9: config 연결 (settings, urls, bootstrap)
10. Step 10: classroom_detail.html 버튼
11. Step 11: preview_modal.html 라우팅 분기
12. Step 12: 테스트 작성

---

## 7. 완료 기준 (Definition of Done)

- [ ] `python manage.py check` 통과
- [ ] `python manage.py test seed_quiz` 전체 통과
- [ ] 교사 원클릭 생성 → QA → 배포 E2E 정상
- [ ] 학생 태블릿 (가로/세로) UI 넘침 없음, 확대 금지 동작
- [ ] 중복 제출 → 보상 1회만 (HSSeedLedger unique constraint)
- [ ] AI 실패 시 fallback 자동 전환 (로그 확인)
- [ ] 동의 미완료 학생 결과 메시지 정확
- [ ] ensure_seed_quiz 실행 후 Product 등록 확인
