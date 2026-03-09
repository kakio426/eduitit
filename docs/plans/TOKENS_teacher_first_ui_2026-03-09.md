# Teacher-First UI Tokens

작성일: 2026-03-09

## Goal
- 설명을 늘리지 않고도 같은 제품처럼 읽히는 공통 UI 문법을 만든다.

## Button Hierarchy
- Primary: 지금 바로 하는 핵심 작업 1개만 사용한다. 채운 배경 + 진한 색 + 굵은 라벨.
- Secondary: 다음 화면으로 넘어가는 보조 작업. 테두리 버튼.
- Tertiary: 설정, 관리, 정리, 더보기. 텍스트 또는 약한 outline.
- Danger: 삭제, 해제, 초기화. 기본 화면 전면 배치 금지.

## Card Spacing
- 메인 작업 카드: `rounded-3xl`, 내부 패딩 `p-5` 이상
- 보조 카드: `rounded-2xl`, 내부 패딩 `p-4`
- 희소 기능 묶음: 기본 접힘 또는 `p-4` 이하의 보조 카드
- 같은 섹션 내 카드 간격: `gap-3` 기본, 섹션 간격은 `space-y-4` 이상

## State Color
- Ready / Primary: indigo
- Success / Completed: emerald
- Warning / Needs review: amber
- Error / Blocking: rose
- Muted / Secondary metadata: slate

## Modal / Drawer Pattern
- 확인/결과/짧은 편집: modal
- 설정/공유/협업/운영: drawer 또는 접힘 패널
- 주 작업 위에 큰 설명 박스는 금지하고, 설정은 본문 밖 2차 위치로 보낸다.

## Empty / Success / Error Pattern
- Empty: 한 줄 제목 + 한 줄 다음 행동만 둔다.
- Success: 완료 사실 + 다음 행동 1개만 둔다.
- Error: 왜 안 됐는지 + 지금 할 수 있는 행동 1개만 둔다.
- 세 상태 모두 긴 안내 문단 금지.

## Naming Rule
- 전면 표기는 작업명 우선, 브랜드명은 보조.
- 교사에게 익숙한 단어 우선: `표`, `줄`, `항목`, `달력`, `안내문`, `서명`, `동의`, `예약`
- `grid`, `column`, `workflow`, `bundle` 같은 내부 용어는 문서/코드 안에만 둔다.

## CTA Rule
- 한 화면에서 같은 목적의 CTA를 여러 개 전면 배치하지 않는다.
- 공유/협업/연동/관리 CTA는 기본 화면 주인공이 되지 않는다.
- 모바일에서는 드래그보다 탭/버튼 기반 조작을 우선한다.
