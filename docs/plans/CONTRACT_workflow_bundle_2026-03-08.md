# Workflow Bundle Contract (2026-03-08)

## Goal
Teacher-first 서비스 묶음이 `도구 전환`이 아니라 `업무 이어서 하기`처럼 동작하도록 seed 계약을 고정합니다.

## Session Keys
- canonical: `workflow_action_seeds`
- compatibility: `workflow_action_seeds`

현재 구현은 두 키에 같은 seed를 함께 저장합니다. 기존 `classroom_workspace` 연동은 그대로 유지하고, 새 서비스 연동은 canonical key를 우선으로 봅니다.

## Seed Shape
```json
{
  "action": "consent|signature|notice|parentcomm_notice",
  "data": {
    "origin_service": "noticegen",
    "origin_url": "/noticegen/",
    "origin_label": "안내문 멘트 생성기로 돌아가기",
    "source_label": "안내문 멘트에서 가져온 내용을 먼저 채워두었어요.",
    "title": "...",
    "message": "...",
    "description": "...",
    "document_title": "...",
    "participants_text": "...",
    "keywords": ["..."],
    "action_type": "notice|parentcomm_notice"
  },
  "created_at": "ISO8601"
}
```

## Current Bundle Coverage
- `noticegen -> consent:create_step1` (validated)
- `noticegen -> signatures:create` (validated)
- `classroom_workspace -> noticegen/consent/signatures` legacy seed compatibility 유지 (validated)
- `reservations -> noticegen` (validated)
- `reservations -> parentcomm` (validated)

## UX Rules
- follow-up CTA 문구는 `이어서 하기` 기준으로 쓴다.
- 원본 서비스 복귀 링크는 seed의 `origin_url`, `origin_label`을 그대로 사용한다.
- prefill 안내 문구는 서비스명보다 `어디서 가져온 내용인지`를 짧게 설명한다.
- 예약 후속 액션은 예약 결과 화면의 교사용 CTA로만 노출하고, 관리자용 조작 버튼과 섞지 않는다.
