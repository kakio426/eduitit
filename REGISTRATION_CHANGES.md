# 회원가입 및 관리자 페이지 개선 사항

## 1. 회원가입 시 필수 정보 추가
- **이메일 필수**: 이제 회원가입 시 `이메일` 입력란이 필수로 변경되었습니다. (`ACCOUNT_EMAIL_REQUIRED = True`)
- **별명 필수**: `CustomSignupForm`을 적용하여 회원가입 시 `별명(Nickname)`을 반드시 입력해야 가입이 완료됩니다.
- **별명 저장 위치**: 사용자가 입력한 별명은 `UserProfile` 테이블의 `nickname` 필드에 저장됩니다.

## 2. 관리자(Admin) 페이지 개선
- **사용자 관리 통합**: `/admin/auth/user/` 페이지에서 사용자를 클릭하면, 하단에 `User Profile` 섹션이 표시됩니다.
- **확인 가능한 정보**:
    - **Nickname (별명)**
    - **Role (역할)**
    - **API Keys**
- 이제 사용자의 기본 정보(ID, 이메일)와 프로필 정보(별명, 역할)를 한 페이지에서 조회하고 수정할 수 있습니다.

## 3. 기술적 변경 사항
- **`core/signup_forms.py` 생성**: 순환 참조 오류(Circular Import)를 방지하기 위해 회원가입 폼을 별도 파일로 분리하였습니다.
- **`core/admin.py` 수정**: `UserProfileInline`을 사용자 관리 화면에 추가하였습니다.
- **`config/settings.py` 수정**: `ACCOUNT_SIGNUP_FORM_CLASS`를 새로운 폼 경로(`core.signup_forms.CustomSignupForm`)로 지정하였습니다.
