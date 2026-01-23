# 코딩 스타일

## 불변성 (필수)

항상 새 객체 생성, 절대 뮤테이션 금지:

```javascript
// 잘못됨: 뮤테이션
function updateUser(user, name) {
  user.name = name  // 뮤테이션!
  return user
}

// 올바름: 불변성
function updateUser(user, name) {
  return {
    ...user,
    name
  }
}
```

## 파일 구성

작은 파일 여러 개 > 큰 파일 소수:
- 높은 응집도, 낮은 결합도
- 일반적으로 200-400줄, 최대 800줄
- 큰 컴포넌트에서 유틸리티 추출
- 타입별이 아닌 기능/도메인별로 구성

## 에러 처리

항상 포괄적으로 에러 처리:

```typescript
try {
  const result = await riskyOperation()
  return result
} catch (error) {
  console.error('작업 실패:', error)
  throw new Error('사용자 친화적인 상세 메시지')
}
```

## 입력 검증

항상 사용자 입력 검증:

```typescript
import { z } from 'zod'

const schema = z.object({
  email: z.string().email(),
  age: z.number().int().min(0).max(150)
})

const validated = schema.parse(input)
```

## 코드 품질 체크리스트

작업 완료 표시 전:
- [ ] 코드가 읽기 쉽고 이름이 적절함
- [ ] 함수가 작음 (<50줄)
- [ ] 파일이 집중됨 (<800줄)
- [ ] 깊은 중첩 없음 (>4단계)
- [ ] 적절한 에러 처리
- [ ] console.log 문 없음
- [ ] 하드코딩된 값 없음
- [ ] 뮤테이션 없음 (불변 패턴 사용)
