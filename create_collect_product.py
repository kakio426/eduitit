
import os
import sys
import django

# Add project root to sys.path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from products.models import Product

def create_collect_product():
    print("Checking for 'Collect' product...")
    
    # Try to find existing product
    product = Product.objects.filter(title__icontains="간편 수합").first()
    
    if product:
        print(f"Product already exists: {product.title}")
        return

    print("Creating 'Collect' product...")
    
    product = Product.objects.create(
        title="간편 수합",
        lead_text="QR 코드 하나로 파일·링크·텍스트를 간편하게 수합하세요!",
        description="여러 선생님으로부터 파일이나 정보를 수합해야 할 때, 메신저로 하나하나 받지 마세요.\n수합 요청을 만들고 QR/코드를 공유하면, 참여자들은 비로그인으로 파일·링크·텍스트를 제출합니다.\n한 화면에서 모든 제출물을 확인하고 다운로드하세요!",
        price=0,
        is_active=True,
        is_featured=False,
        is_guest_allowed=True,
        icon="📋",
        color_theme="green",
        card_size="small",
        service_type="work",  # 업무경감
        display_order=10
    )
    
    print(f"Product created successfully: {product.title}")

if __name__ == '__main__':
    create_collect_product()
