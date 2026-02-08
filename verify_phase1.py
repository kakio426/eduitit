import os
import django
import sys

# Django 설정
sys.path.insert(0, r'c:\Users\kakio\eduitit')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from studentmbti.models import TestSession
from django.contrib.auth.models import User

# 테스트 세션 생성
teacher = User.objects.first()
if not teacher:
    print("ERROR: No user found in database")
    sys.exit(1)

session = TestSession.objects.create(
    teacher=teacher,
    session_name='Test Numeric Code Verification'
)

print(f"✓ Session Created: {session.id}")
print(f"✓ Access Code: {session.access_code}")
print(f"✓ Is Numeric Only: {session.access_code.isdigit()}")
print(f"✓ Length: {len(session.access_code)}")
print(f"✓ Expected: 6-digit numeric code")

# 검증
if session.access_code.isdigit() and len(session.access_code) == 6:
    print("\n✅ PHASE 1 VERIFICATION PASSED: Join code is numeric-only!")
else:
    print("\n❌ PHASE 1 VERIFICATION FAILED")

# 정리
session.delete()
print("\n✓ Test session deleted")
