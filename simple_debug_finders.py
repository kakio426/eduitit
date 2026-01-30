import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_production')
django.setup()

from django.contrib.staticfiles import finders
from django.conf import settings

target = 'admin/css/base.css'
result = finders.find(target)
print(f"RESULT: {result}")
