# Eduitit LLM Dataset

이 폴더는 `eduitit` 코드베이스를 기준으로 LLM 대화/학습용 데이터를 자동 생성한 결과물입니다.

## 생성 파일

- `eduitit_service_catalog.json`
  - 서비스(Product) 중심 메타데이터
  - 제목/설명/카테고리/런치 라우트/앱 매핑 정보 포함
- `eduitit_code_structure.json`
  - Django 앱 중심 코드 구조 인덱스
  - 모델/뷰/URL 패턴/템플릿·정적파일·마이그레이션 수 포함
- `eduitit_chat_training.jsonl`
  - LLM 학습용 대화 샘플(JSONL)
  - 각 서비스당 2개 샘플
  - `service_overview`, `code_structure` 태스크 포함

## 재생성 방법

프로젝트 루트에서:

```powershell
python scripts/generate_llm_training_data.py
```

## 권장 사용 방식

1. 빠른 도메인 응답용 RAG:
   - `eduitit_service_catalog.json` + `eduitit_code_structure.json`를 청크 단위 임베딩
   - 사용자 질문 시 관련 서비스/앱 문서를 우선 검색해 컨텍스트로 주입

2. 미세조정(Fine-tuning)용:
   - `eduitit_chat_training.jsonl`을 학습 데이터로 사용
   - 운영 전에는 내부 검수 질문셋으로 환각 여부 점검 권장

## 주의사항

- 이 데이터는 현재 로컬 코드/DB 스냅샷 기준입니다.
- DB 기반 서비스 메타데이터(`products_product`)가 바뀌면 결과도 달라집니다.
- 신규 서비스 추가/라우트 변경 후에는 반드시 재생성하세요.
