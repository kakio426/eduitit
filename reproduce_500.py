import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import RequestFactory
from fortune.views import saju_view

factory = RequestFactory()
from django.contrib.auth.models import AnonymousUser
request = factory.get('/fortune/')
request.user = AnonymousUser()

try:
    response = saju_view(request)
    print(f"Status: {response.status_code}")
except Exception:
    import traceback
    with open('reproduction_error.txt', 'w', encoding='utf-8') as f:
        f.write(traceback.format_exc())
    print("Error written to reproduction_error.txt")
