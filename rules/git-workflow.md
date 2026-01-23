# Git 워크플로우

## 브랜치 전략

```
main (또는 master)
  └── develop
       ├── feature/기능명
       ├── fix/버그명
       └── refactor/대상
```

## 커밋 메시지 형식

```
[타입] 제목 (50자 이내)

본문 (선택, 72자 줄바꿈)
- 무엇을 변경했는지
- 왜 변경했는지

Co-Authored-By: Claude <noreply@anthropic.com>
```

### 타입
- `feat`: 새 기능
- `fix`: 버그 수정
- `docs`: 문서 변경
- `style`: 포맷팅 (코드 변경 없음)
- `refactor`: 리팩토링
- `test`: 테스트 추가/수정
- `chore`: 빌드, 설정 변경

## PR 체크리스트

- [ ] 테스트 통과
- [ ] 린트 통과
- [ ] 타입 체크 통과
- [ ] 리뷰어 지정
- [ ] 관련 이슈 연결

## 금지 사항

- main/master에 직접 push 금지
- force push 금지 (특별한 경우 제외)
- 대용량 바이너리 커밋 금지
- .env 파일 커밋 금지
