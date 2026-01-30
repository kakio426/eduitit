import os
import sys
from io import StringIO
from django.core.management import call_command

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_production')
import django
django.setup()

print("Running collectstatic with verbosity 3...")
try:
    # Use real stdout for a moment to see if it makes a difference, or just capture it.
    call_command('collectstatic', interactive=False, verbosity=3, clear=True)
    print("\nSUCCESS")
except Exception as e:
    print(f"\nERROR: {e}")
