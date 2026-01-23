# Schoolit Integration Guide (SSO)

This guide explains how to implement the SSO receiver in the `schoolit` (NestJS) backend to handle the login token from `eduitit`.

## 1. Environment Variables in Schoolit
Add the following to your `schoolit` backend `.env` file:
```env
SSO_JWT_SECRET="에듀이티잇의 settings.py에 설정된 것과 동일한 시크릿 키"
```

## 2. Implement SSO Guard in NestJS
Create a new guard or modify the existing auth guard to handle the `sso_token` query parameter.

```typescript
// apps/backend/src/auth/guards/sso.guard.ts
import { Injectable, CanActivate, ExecutionContext, UnauthorizedException } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';

@Injectable()
export class SSOGuard implements CanActivate {
  constructor(
    private jwtService: JwtService,
    private configService: ConfigService,
  ) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const request = context.switchToHttp().getRequest();
    const token = request.query.sso_token;

    if (!token) return true; // SSO 토큰이 없으면 일반 인증 흐름으로

    try {
      const payload = await this.jwtService.verifyAsync(token, {
        secret: this.configService.get('SSO_JWT_SECRET'),
      });
      
      // 토큰 정보를 바탕으로 유저 세션 생성 로직
      // payload.username, payload.role 등을 사용
      request['user'] = payload; 
      return true;
    } catch {
      throw new UnauthorizedException('Invalid SSO Token');
    }
  }
}
```

## 3. Frontend Landing Logic (Next.js)
`schoolit`의 프론트엔드에서는 URL 파라미터를 감지하여 자동으로 배정된 페이지로 이동하거나 로그인을 처리합니다.

```javascript
// 예시: useEffect에서 sso_token 감지
useEffect(() => {
  const urlParams = new URLSearchParams(window.location.search);
  const token = urlParams.get('sso_token');
  if (token) {
    // 백엔드 API를 호출하여 세션 쿠키/JWT 설정
    loginWithSSO(token);
  }
}, []);
```

## 4. Mapping Roles to Landing Pages
`eduitit`에서는 다음 규칙으로 리다이렉트합니다:
- **school**: `schoolit.com/school/dashboard`
- **instructor**: `schoolit.com/instructor/jobs`
- **company**: `schoolit.com/company/events`
