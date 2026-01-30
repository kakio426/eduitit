import os
import sys
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_production')
import django
from django.conf import settings

print(f"BASE_DIR: {settings.BASE_DIR}")
print(f"STATIC_ROOT: {settings.STATIC_ROOT}")
print(f"STATIC_URL: {settings.STATIC_URL}")
print(f"FileSystemStorage location: {settings.STATIC_ROOT.resolve()}")

# Check if directory exists
if settings.STATIC_ROOT.exists():
    print(f"Directory exists: True")
    print(f"Contents: {list(settings.STATIC_ROOT.glob('*'))}")
else:
    print(f"Directory exists: False")
