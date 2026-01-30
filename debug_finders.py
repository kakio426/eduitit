import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_production')
django.setup()

from django.contrib.staticfiles import finders
from django.conf import settings

print(f"STATIC_ROOT: {settings.STATIC_ROOT}")
print(f"STATICFILES_DIRS: {settings.STATICFILES_DIRS}")
print(f"INSTALLED_APPS: {len(settings.INSTALLED_APPS)} apps")

target = 'admin/css/base.css'
result = finders.find(target)

if result:
    print(f"FOUND {target} at: {result}")
else:
    print(f"NOT FOUND {target}")

for finder in finders.get_finders():
    print(f"Finder: {finder}")
    # Try to list some files from this finder
    if hasattr(finder, 'list'):
        count = 0
        for path, storage in finder.list([]):
            count += 1
            if count < 5:
                print(f"  - {path}")
        print(f"  Total files in finder: {count}")
