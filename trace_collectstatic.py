import os
import sys
from io import StringIO
from django.core.management import call_command

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_production')
import django
django.setup()

from django.conf import settings
print(f"DEBUG: STATIC_ROOT is {os.path.abspath(settings.STATIC_ROOT)}")

with open('collectstatic_trace.log', 'w', encoding='utf-8') as f:
    f.write(f"STATIC_ROOT: {os.path.abspath(settings.STATIC_ROOT)}\n")
    f.write(f"STATICFILES_DIRS: {settings.STATICFILES_DIRS}\n")
    f.write("-" * 50 + "\n")
    
    # Run command and pipe output directly to file
    sys.stdout = f
    sys.stderr = f
    try:
        call_command('collectstatic', interactive=False, verbosity=3)
        print("\nSUCCESS")
    except Exception as e:
        print(f"\nERROR: {e}")

print("Trace saved to collectstatic_trace.log")
