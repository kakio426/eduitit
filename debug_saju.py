
import os
import django
import sys

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from fortune.views import generate_ai_response
from django.test import RequestFactory
from unittest.mock import MagicMock

def debug():
    factory = RequestFactory()
    request = factory.post('/fortune/api/streaming/')
    request.user = MagicMock()
    request.user.is_authenticated = False
    
    prompt = "안녕하세요, 사주 분석 부탁드립니다."
    
    print("--- Starting AI Response Generation ---")
    try:
        generator = generate_ai_response(prompt, request)
        for chunk in generator:
            print(chunk, end='', flush=True)
    except Exception as e:
        print(f"\nCaught Exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug()
