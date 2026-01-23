# 보안 가이드라인

## 필수 보안 검사

모든 커밋 전:
- [ ] 하드코딩된 시크릿 없음 (API 키, 비밀번호, 토큰)
- [ ] 모든 사용자 입력 검증됨
- [ ] SQL 인젝션 방지 (파라미터화된 쿼리)
- [ ] XSS 방지 (HTML 이스케이프)
- [ ] CSRF 보호 활성화
- [ ] 인증/권한 검증됨
- [ ] 에러 메시지에 민감 정보 노출 없음

## 시크릿 관리

```typescript
// 절대 금지: 하드코딩된 시크릿
const apiKey = "sk-proj-xxxxx"

// 항상: 환경 변수 사용
const apiKey = process.env.OPENAI_API_KEY

if (!apiKey) {
  throw new Error('OPENAI_API_KEY가 설정되지 않았습니다')
}
```

## 보안 이슈 발견 시

1. 즉시 작업 중단
2. **security-reviewer** 에이전트 사용
3. 심각한 이슈 먼저 수정
4. 노출된 시크릿 교체
5. 전체 코드베이스에서 유사 이슈 검토
