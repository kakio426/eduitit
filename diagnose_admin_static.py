import os
import django
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_production')
django.setup()

from django.conf import settings

print("=" * 60)
print("Django Admin Static Files Diagnostic")
print("=" * 60)

# 1. Settings Check
print("\n[1] Static Files Settings:")
print(f"  - STATIC_URL: {settings.STATIC_URL}")
print(f"  - STATIC_ROOT: {settings.STATIC_ROOT}")
print(f"  - STATICFILES_STORAGE: {settings.STATICFILES_STORAGE}")

if hasattr(settings, 'STORAGES'):
    print(f"  - STORAGES['staticfiles']: {settings.STORAGES.get('staticfiles', {}).get('BACKEND', 'Not set')}")

# 2. Static Root Directory Check
print(f"\n[2] STATIC_ROOT Directory:")
if settings.STATIC_ROOT.exists():
    print(f"  ✓ Exists: {settings.STATIC_ROOT}")
    print(f"  - Writable: {os.access(settings.STATIC_ROOT, os.W_OK)}")
    
    # Count files
    file_count = sum(1 for _ in settings.STATIC_ROOT.rglob('*') if _.is_file())
    print(f"  - Total files: {file_count}")
else:
    print(f"  ✗ Does NOT exist: {settings.STATIC_ROOT}")

# 3. Admin Static Files Check
admin_css = settings.STATIC_ROOT / 'admin' / 'css' / 'base.css'
print(f"\n[3] Admin CSS Files:")
if admin_css.exists():
    print(f"  ✓ base.css exists: {admin_css}")
    print(f"  - Size: {admin_css.stat().st_size} bytes")
else:
    print(f"  ✗ base.css NOT FOUND: {admin_css}")
    print(f"  → Run: python manage.py collectstatic --noinput")

# 4. WhiteNoise Check
print(f"\n[4] WhiteNoise Configuration:")
middleware = settings.MIDDLEWARE
whitenoise_index = next((i for i, m in enumerate(middleware) if 'whitenoise' in m.lower()), None)
if whitenoise_index is not None:
    print(f"  ✓ WhiteNoise middleware found at index {whitenoise_index}")
    print(f"  - Position: {middleware[whitenoise_index]}")
    
    # Check if it's after SecurityMiddleware
    security_index = next((i for i, m in enumerate(middleware) if 'SecurityMiddleware' in m), None)
    if security_index is not None and whitenoise_index == security_index + 1:
        print(f"  ✓ Correctly positioned after SecurityMiddleware")
    else:
        print(f"  ⚠️  May not be in optimal position")
else:
    print(f"  ✗ WhiteNoise middleware NOT FOUND")

# 5. Recommendations
print(f"\n[5] Recommendations:")
if not settings.STATIC_ROOT.exists():
    print("  → Create STATIC_ROOT directory and run collectstatic")
elif not admin_css.exists():
    print("  → Run: python manage.py collectstatic --noinput --clear")
else:
    print("  ✓ Static files appear to be configured correctly")
    print("  → Check Railway deployment logs for collectstatic errors")

print("\n" + "=" * 60)
