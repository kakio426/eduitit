# Seed Quiz LLM Pack (GEMS/GPT 공용)

아래 파일 3개를 그대로 복사해서 사용하면 됩니다.

1. `gems_gpt_system_instruction_ko.txt`
- GEMS/GPT의 시스템 지침(커스텀 지침)에 넣는 내용

2. `user_prompt_template_ko.txt`
- 매번 요청할 때 쓰는 사용자 프롬프트 템플릿

3. `topic_reference.tsv`
- `주제`에 넣을 수 있는 한글 이름/코드 참고표

4. `output_example.tsv`
- 정답 형식 예시

## 권장 사용법

1. GEMS/GPT 시스템 지침에 `gems_gpt_system_instruction_ko.txt`를 넣습니다.
2. 요청 시 `user_prompt_template_ko.txt`를 복사해 값만 바꿉니다.
3. 결과를 TSV 그대로 복사합니다.
4. Seed Quiz에 붙여넣거나(빠른개선 기능), CSV/XLSX로 옮겨 업로드합니다.

## 출력 형식(중요)

- 출력은 반드시 `탭(\\t)` 구분 TSV
- 첫 줄 헤더는 아래와 정확히 동일

`주제	학년	문제	보기1	보기2	보기3	보기4	정답번호	해설	난이도`

- 허용 난이도: `쉬움`, `보통`, `어려움`
- 정답번호: `1~4`
- 한 파일(한 번 업로드)에서는 주제/학년을 섞지 않습니다.

