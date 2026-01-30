import os
import django
from django.conf import settings
from django.contrib.staticfiles import finders
from collections import Counter

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_production')
django.setup()

with open('final_debug.txt', 'w', encoding='utf-8') as f:
    f.write(f"STATIC_ROOT: {settings.STATIC_ROOT}\n")
    f.write(f"STATICFILES_DIRS: {settings.STATICFILES_DIRS}\n")
    
    found_files = []
    for finder in finders.get_finders():
        for path, storage in finder.list([]):
            found_files.append(path)
    
    f.write(f"Total files found in source: {len(found_files)}\n")
    admin_files = [x for x in found_files if x.startswith('admin')]
    f.write(f"Admin files found: {len(admin_files)}\n")
    
    counts = Counter(found_files)
    duplicates = [x for x, count in counts.items() if count > 1]
    f.write(f"Duplicate files count: {len(duplicates)}\n")
    if duplicates:
        f.write(f"Sample duplicate: {duplicates[0]}\n")
    
    # Check if target exists
    f.write(f"Target dir exists: {os.path.exists(settings.STATIC_ROOT)}\n")
