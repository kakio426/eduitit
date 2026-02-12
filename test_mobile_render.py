import os
import django
from dotenv import load_dotenv

# 1. 환경 설정 및 장고 초기화
load_dotenv()
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# 2. 장고 로드 후 필요한 모듈 임포트
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from reservations.views import reservation_index
from reservations.models import School

def test_mobile_view():
    factory = RequestFactory()
    
    # 데이터베이스에서 학교 하나 가져오기
    school = School.objects.first()
    if not school:
        print("Error: No school found in database to test.")
        return

    print(f"Testing mobile view for school: {school.name} (slug: {school.slug})")

    # 모바일 User-Agent
    mobile_ua = 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
    request = factory.get(f'/reservations/{school.slug}/', HTTP_USER_AGENT=mobile_ua)
    
    # 유저 및 세션 설정
    request.user = AnonymousUser()
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(request)
    request.session.save()

    # htmx 모킹
    class MockHtmx:
        def __init__(self):
            self.boosted = False
        def __bool__(self):
            return False
    request.htmx = MockHtmx()

    # 뷰 렌더링 호출
    try:
        response = reservation_index(request, school.slug)
        print(f"Response Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("SUCCESS: Mobile view rendered successfully!")
            content = response.content.decode('utf-8')
            if 'lg:hidden' in content:
                print("Confirmed: Mobile layout (lg:hidden) is present.")
        else:
            print(f"FAILED: Status code {response.status_code}")
            
    except Exception as e:
        import traceback
        print("CRITICAL ERROR during rendering:")
        print(traceback.format_exc())

if __name__ == "__main__":
    test_mobile_view()
