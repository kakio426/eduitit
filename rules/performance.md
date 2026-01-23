# 성능 가이드라인

## 프론트엔드

### React 최적화
```typescript
// 메모이제이션 사용
const MemoizedComponent = React.memo(Component);
const memoizedValue = useMemo(() => compute(a, b), [a, b]);
const memoizedCallback = useCallback(() => fn(a), [a]);
```

### 번들 최적화
- 코드 스플리팅 사용 (`React.lazy`)
- 트리 쉐이킹 확인
- 이미지 최적화 (WebP, lazy loading)

## 백엔드

### 데이터베이스
- 인덱스 적절히 사용
- N+1 쿼리 방지
- 페이지네이션 구현
- 쿼리 결과 캐싱

### API
- 응답 압축 (gzip)
- 적절한 캐시 헤더
- 페이지네이션 필수

## 성능 체크리스트

- [ ] O(n²) 이상 알고리즘 검토
- [ ] 불필요한 리렌더링 제거
- [ ] 메모이제이션 적용
- [ ] 번들 사이즈 확인
- [ ] DB 쿼리 최적화
- [ ] 캐싱 전략 적용
