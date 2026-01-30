import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_production')
import django
django.setup()
from django.conf import settings

print(f"INSTALLED_APPS count: {len(settings.INSTALLED_APPS)}")
found_admin = False
for app in settings.INSTALLED_APPS:
    print(f"- {app}")
    if app == 'django.contrib.admin':
        found_admin = True

if found_admin:
    print("\n✅ django.contrib.admin is PRESENT")
else:
    print("\n❌ django.contrib.admin is MISSING")
