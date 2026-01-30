import os
import sys
from pathlib import Path

# Suppress Django setup warnings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_production')

import django
django.setup()

from django.conf import settings

# Check admin static files
admin_css = settings.STATIC_ROOT / 'admin' / 'css' / 'base.css'

print("\n=== ADMIN STATIC FILES CHECK ===\n")
print(f"STATIC_ROOT: {settings.STATIC_ROOT}")
print(f"Exists: {settings.STATIC_ROOT.exists()}")

if settings.STATIC_ROOT.exists():
    file_count = sum(1 for _ in settings.STATIC_ROOT.rglob('*') if _.is_file())
    print(f"Total files: {file_count}")
    
    print(f"\nAdmin base.css: {admin_css}")
    print(f"Exists: {admin_css.exists()}")
    
    if not admin_css.exists():
        print("\n❌ PROBLEM: Admin CSS files not collected!")
        print("→ Run: python manage.py collectstatic --noinput")
    else:
        print(f"Size: {admin_css.stat().st_size} bytes")
        print("\n✅ Admin static files OK")
else:
    print("\n❌ PROBLEM: STATIC_ROOT directory does not exist!")
    print("→ Run: python manage.py collectstatic --noinput")
