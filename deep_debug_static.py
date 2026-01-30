import os
import django
from django.conf import settings
from django.contrib.staticfiles import finders

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_production')
django.setup()

print(f"STATIC_ROOT: {settings.STATIC_ROOT}")
print(f"STATICFILES_DIRS: {settings.STATICFILES_DIRS}")

found_files = []
for finder in finders.get_finders():
    for path, storage in finder.list([]):
        found_files.append(path)

print(f"Total files found in source: {len(found_files)}")
admin_files = [f for f in found_files if f.startswith('admin')]
print(f"Admin files found: {len(admin_files)}")

# Check for duplicates
from collections import Counter
counts = Counter(found_files)
duplicates = [f for f, count in counts.items() if count > 1]
print(f"Duplicate files (potential conflicts): {len(duplicates)}")
if duplicates:
    print(f"Sample duplicate: {duplicates[0]}")
