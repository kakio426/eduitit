import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_production')
django.setup()

def run():
    from products.models import Product
    from insights.models import Insight
    from django.contrib.auth.models import User

    # Create superuser if it doesn't exist
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'admin1234')
        print("Superuser 'admin' created successfully!")

    # Only seed data if database is empty (first-time setup)
    if Product.objects.exists():
        print("Database already has products. Skipping seed data to preserve existing data.")
        return
    
    print("Database is empty. Seeding initial data...")
    
    # 1. Seed Insights
    Insight.objects.create(
        title="AI 시대, 교사의 역할은 어떻게 변할까?",
        video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        content="지식의 전달자에서 영감의 설계자로.",
        kakio_note="이 영상은 AI 도구를 수업에 녹여내는 구체적인 방법을 제시합니다. 꼭 확인해보세요.",
        tags="#FutureEducation",
        is_featured=True
    )
    
    Insight.objects.create(
        title="ChatGPT를 활용한 행정 업무 혁명",
        video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        content="업무 자동화가 가져올 교실의 변화.",
        kakio_note="단순 반복 업무에서 벗어날 때 아이들과의 시간이 늘어납니다.",
        tags="#Productivity",
        is_featured=True
    )
    
    # 2. Seed All Products/Services
    # Seed Products with display metadata
    Product.objects.create(
        title="🐎 온라인 윷놀이",
        description="설치 없이 바로 즐기는 학급 대항전 필수템!",
        price=0,
        is_active=True,
        is_featured=True,
        icon="🎲",
        color_theme="green",
        service_type="game",
        display_order=1,
        image="https://placehold.co/600x400/green/white?text=Yut+Noli"
    )
    
    Product.objects.create(
        title="HWP to PDF Converter",
        description="HWP 파일을 즉시 PDF로 변환하는 도구입니다.",
        price=15000,
        is_active=True,
        icon="📄",
        color_theme="blue",
        service_type="tool",
        display_order=2,
        image="https://placehold.co/600x400/purple/white?text=HWP+to+PDF"
    )
    
    Product.objects.create(
        title="Automated Article Creator",
        description="AI를 활용해 전문적인 기사와 블로그 포스트를 생성합니다.",
        price=25000,
        is_active=True,
        icon="📰",
        color_theme="green",
        service_type="tool",
        display_order=3,
        image="https://placehold.co/600x400/blue/white?text=AI+Article"
    )

    Product.objects.create(
        title="PlayAura",
        description="전세계 인기 영상 탐험 및 AI 분석 도구",
        price=0,
        is_active=True,
        icon="fa-brands fa-youtube",
        color_theme="red",
        service_type="platform",
        display_order=4,
        external_url="https://playaura.com",  # 실제 URL로 변경 필요
        image="https://placehold.co/600x400/red/white?text=PlayAura"
    )

    Product.objects.create(
        title="스쿨잇 (Schoolit)",
        description="선생님과 학생을 위한 스마트 교육 공동체 플랫폼",
        price=0,
        is_active=True,
        icon="fa-solid fa-school",
        color_theme="orange",
        service_type="platform",
        display_order=5,
        external_url="https://schoolit.kr",  # 실제 URL로 변경 필요
        image="https://placehold.co/600x400/orange/white?text=Schoolit"
    )

    # Core Services (previously hardcoded)
    Product.objects.create(
        title="인사이트",
        description="영감 보석함",
        price=0,
        is_active=True,
        icon="fa-solid fa-gem",
        color_theme="purple",
        service_type="library",
        card_size="small",
        display_order=6,
        external_url="/insights/",
        image="https://placehold.co/600x400/purple/white?text=Insights"
    )

    Product.objects.create(
        title="AI 도구 가이드",
        description="상황별로 딱 맞는 AI 도구를 추천해드려요.",
        price=0,
        is_active=True,
        icon="fa-solid fa-robot",
        color_theme="dark",
        service_type="guide",
        card_size="tall",
        display_order=7,
        external_url="/tools/",
        image="https://placehold.co/600x400/gray/white?text=AI+Tools"
    )

    Product.objects.create(
        title="AI 프롬프트 레시피",
        description="생기부, 가정통신문, 수업지도안... 복사해서 바로 쓰는 검증된 주문서.",
        price=0,
        is_active=True,
        icon="fa-solid fa-wand-magic-sparkles",
        color_theme="purple",
        service_type="tool",
        card_size="wide",
        display_order=8,
        external_url="/prompts/",
        image="https://placehold.co/600x400/purple/white?text=Prompt+Lab"
    )
    
    print("All service data, Insights, and Admin account successfully seeded!")

if __name__ == '__main__':
    run()
