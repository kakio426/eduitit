import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from django.contrib import admin
from core.models import UserProfile
from core.signup_forms import CustomSignupForm

print("=== 1. Settings Verification ===")
print(f"ACCOUNT_EMAIL_REQUIRED: {getattr(settings, 'ACCOUNT_EMAIL_REQUIRED', 'Not Set')}")
print(f"ACCOUNT_SIGNUP_FORM_CLASS: {getattr(settings, 'ACCOUNT_SIGNUP_FORM_CLASS', 'Not Set')}")
print(f"ACCOUNT_SIGNUP_FIELDS: {getattr(settings, 'ACCOUNT_SIGNUP_FIELDS', 'Not Set')}")

print("\n=== 2. Form Verification ===")
form = CustomSignupForm()
print(f"Form Fields: {list(form.fields.keys())}")
if 'nickname' in form.fields and form.fields['nickname'].required:
    print("PASS: 'nickname' field exists and is required.")
else:
    print("FAIL: 'nickname' validation failed.")

print("\n=== 3. Model Verification ===")
try:
    field = UserProfile._meta.get_field('nickname')
    print(f"PASS: UserProfile has 'nickname' field: {field}")
    print(f"Storage Table: {UserProfile._meta.db_table}")
except Exception as e:
    print(f"FAIL: UserProfile model check failed: {e}")

print("\n=== 4. Admin Verification ===")
if User in admin.site._registry:
    user_admin = admin.site._registry[User]
    print(f"User Admin Registered: {user_admin}")
    inline_instances = user_admin.inlines
    names = [inline.__name__ for inline in inline_instances] if inline_instances else []
    print(f"User Admin Inlines: {names}")
    if 'UserProfileInline' in str(names):
        print("PASS: UserProfileInline is attached to UserAdmin.")
    else:
        # It might be the class object itself
        if any('UserProfileInline' in str(i) for i in inline_instances):
             print("PASS: UserProfileInline is attached to UserAdmin.")
        else:
            print("FAIL: UserProfileInline NOT found.")
else:
    print("FAIL: User is not registered in Admin.")

print("\n=== Verification Complete ===")
