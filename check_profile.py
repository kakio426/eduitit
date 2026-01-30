#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import UserProfile

print("=" * 60)
print("UserProfile 데이터베이스 확인")
print("=" * 60)

try:
    user = User.objects.get(username='kakio')
    profile = user.userprofile

    print(f"\n현재 로그인 사용자: {user.username}")
    print(f"프로필 ID: {profile.id}")
    print(f"별명(nickname): {repr(profile.nickname)}")
    print(f"역할(role): {profile.role}")

except User.DoesNotExist:
    print("\n❌ 'kakio' 사용자를 찾을 수 없습니다.")
except Exception as e:
    print(f"\n❌ 오류: {e}")

print("\n" + "=" * 60)
print("모든 UserProfile 목록")
print("=" * 60)

for prof in UserProfile.objects.all():
    print(f"\n사용자: {prof.user.username}")
    print(f"  - 별명: {repr(prof.nickname)}")
    print(f"  - 역할: {prof.role}")
    print(f"  - Gemini API Key: {'설정됨' if prof.gemini_api_key else '없음'}")
