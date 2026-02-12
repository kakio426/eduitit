import os
import django
import sys

# Django 설정 로드
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from collect.models import CollectionRequest
from django.contrib.auth.models import User
from django.test import RequestFactory
from collect.views import request_create

# 테스트 실행
def test_create():
    user = User.objects.filter(is_superuser=True).first()
    if not user:
        print("No superuser found")
        return
        
    factory = RequestFactory()
    data = {
        'title': 'Test Request',
        'allow_file': 'on',
        'allow_link': 'on',
        'allow_text': 'on',
        'max_submissions': 50,
    }
    request = factory.post('/collect/create/', data)
    request.user = user
    request.FILES = {}
    
    try:
        response = request_create(request)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 302:
            print(f"Redirected to: {response.url}")
        else:
            print("Form invalid or some other response")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_create()
