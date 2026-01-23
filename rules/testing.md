# 테스트 가이드라인

## 테스트 작성 원칙

1. **새 기능 = 새 테스트**: 모든 새 기능에 테스트 필수
2. **버그 수정 = 회귀 테스트**: 버그 수정 시 해당 케이스 테스트 추가
3. **리팩토링 = 기존 테스트 유지**: 테스트가 깨지면 리팩토링 실패

## 테스트 구조

```typescript
describe('기능명', () => {
  // 설정
  beforeEach(() => {
    // 공통 설정
  });

  it('정상 케이스를 처리해야 한다', () => {
    // Arrange
    const input = validInput;

    // Act
    const result = functionUnderTest(input);

    // Assert
    expect(result).toBe(expected);
  });

  it('에러 케이스를 처리해야 한다', () => {
    expect(() => functionUnderTest(invalidInput)).toThrow();
  });
});
```

## 커버리지 목표

- 새 코드: 80% 이상
- 핵심 비즈니스 로직: 90% 이상
- 유틸리티 함수: 100%

## 테스트 명령어

```bash
# 전체 테스트
npm test

# 커버리지 포함
npm test -- --coverage

# 특정 파일
npm test -- path/to/file.test.ts

# watch 모드
npm test -- --watch
```
