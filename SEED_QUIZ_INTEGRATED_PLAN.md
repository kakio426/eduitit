# Seed Quiz 통합 계획안 (CSV 전용 운영)

기준일: 2026-02-21  
운영 원칙: `자동 배치 비활성` + `교사/운영자 검수 후 CSV 업로드`

## 1. 변경 결정 (확정)

1. OpenAI Batch 자동화 파이프라인은 운영에서 사용하지 않는다.
2. 문제 공급은 `CSV 업로드`를 기본으로 한다.
3. 교사 화면은 `주제 중심`으로 운영한다(학년은 선택 보조값).
4. AI 경로는 기본 비활성 상태로 둔다.

## 2. 현재 반영 상태

1. `SEED_QUIZ_BATCH_ENABLED=False` 기본값 반영 완료.
2. 배치 명령(`seed_quiz_batch_submit`, `seed_quiz_batch_collect`, `seed_quiz_batch_tick`)은 위 플래그가 꺼져 있으면 실행 차단.
3. 교사 대시보드에서 RAG 카드는 `SEED_QUIZ_ALLOW_RAG=True`일 때만 노출.
4. 주제(`preset_type`)는 20개로 확장 완료.
5. CSV 파서가 새 주제 키를 검증하도록 반영 완료.
6. 문제은행 조회에서 `전체 학년` 필터 지원 완료.
7. 주제별 랜덤 1세트 선택 기능 반영 완료(최근 사용 세트 우선 제외).
8. CSV 템플릿 다운로드 기능 반영 완료.
9. 주제별 운영 요약(총 세트/공식/공유/검토대기/최근 사용일) 반영 완료.

## 3. 주제 체계 (20개)

1. `orthography` 맞춤법
2. `spacing` 띄어쓰기
3. `vocabulary` 어휘 뜻
4. `proverb` 속담
5. `idiom` 관용어
6. `sino_idiom` 사자성어
7. `hanja_word` 한자어 뜻
8. `main_sentence` 중심문장 찾기
9. `sentence_order` 문장 순서 배열
10. `topic_title` 주제/제목 고르기
11. `fact_opinion` 사실/의견 구분
12. `eng_vocab` 영어 단어 뜻
13. `eng_sentence` 영어 문장 의미
14. `eng_cloze` 영어 빈칸 채우기
15. `arithmetic` 수학 연산
16. `pattern` 규칙 찾기
17. `fraction_decimal` 분수/소수 비교
18. `time_calendar` 시간/달력 계산
19. `unit_conversion` 단위 변환
20. `safety_common` 생활 안전 상식

## 4. CSV 운영 표준

헤더:
`set_title,preset_type,grade,question_text,choice_1,choice_2,choice_3,choice_4,correct_index,explanation,difficulty`

규칙:
1. 한 세트는 정확히 3문항.
2. `set_title` 표준: `SQ-{topic}-basic-L1-G{grade}-S{seq}-V{ver}`.
3. `preset_type`은 위 20개 키만 허용.
4. `correct_index`는 0~3.
5. 선택지 중복/빈값 금지.
6. 업로드 후 반드시 미리보기에서 검수 후 확정.

## 5. 배포 운영 흐름

1. 운영자/교사가 외부 LLM으로 CSV 초안 생성
2. 사람이 검수/수정
3. `CSV 업로드 -> 미리보기 -> 확정 저장`
4. 교사가 주제별/학년별(또는 전체학년)로 은행 조회
5. 선택 후 배포

## 6. 남은 작업 (미완료)

1. 없음 (현재 계획 범위 완료)

## 7. 운영 플래그 기본값

1. `SEED_QUIZ_BATCH_ENABLED=False`
2. `SEED_QUIZ_ALLOW_RAG=False`
3. `SEED_QUIZ_ALLOW_INLINE_AI=False`
