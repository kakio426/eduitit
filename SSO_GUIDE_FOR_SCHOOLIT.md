# Schoolit Integration Guide (SSO) - Revised

이 가이드는 `eduitit`에서 보낸 SSO 토큰을 `schoolit` (NestJS) 백엔드에서 안전하게 처리하기 위한 최종 가이드입니다.

## 1. Environment Variables in Schoolit
`.env` 파일에 다음을 추가하세요:
```env
SSO_JWT_SECRET="eduitit의 settings.py와 동일한 시크릿 키"
SCHOOLIT_DOMAIN="schoolit.shop"
```

## 2. Updated SSO Guard (Security Fixed)
토큰이 없을 경우 예외를 발생시키고 타입 안전성을 강화한 버전입니다.

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

    // 수정: SSO 전용 엔드포인트이므로 토큰 부재 시 즉시 차단
    if (!token) {
      throw new UnauthorizedException('SSO token is missing');
    }

    try {
      const payload = await this.jwtService.verifyAsync(token.toString(), {
        secret: this.configService.get('SSO_JWT_SECRET'),
        algorithms: ['HS256'], // 알고리즘 명시
      });
      
      request['user'] = payload; 
      return true;
    } catch (error) {
      throw new UnauthorizedException('Invalid SSO Token');
    }
  }
}
```

## 3. Payload 필드 구성 정보
`eduitit`은 JWT에 다음 데이터를 실어 보냅니다. `auth.service.ts`에서 이 이름 그대로 사용하면 됩니다.
- `sub`: 유저 고유 ID (string)
- `username`: 이메일 또는 ID
- `email`: 유저 이메일
- `name`: 유저 이름
- `role`: `SCHOOL` | `INSTRUCTOR` | `COMPANY` (대문자)

## 4. Redirect Rules
`schoolit.shop/auth/sso` 페이지에서 토큰 처리 후 다음으로 리다이렉트합니다.
- **SCHOOL**: `/school/dashboard`
- **INSTRUCTOR**: `/instructor/jobs`
- **COMPANY**: `/company/events`
