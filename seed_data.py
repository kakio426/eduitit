import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings_production')
django.setup()

def run():
    from products.models import Product, ProductFeature
    from insights.models import Insight
    from django.contrib.auth.models import User

    # Create superuser if it doesn't exist
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'admin1234')
        print("Superuser 'admin' created successfully!")

    # Force re-seeding for clean state (optional, can be safer for dev)
    if Product.objects.exists():
        print("Database already has products. Deleting existing key products to re-seed feature data...")
        # Only delete specific seeded products to avoid wiping real user data if any
        Product.objects.filter(title__in=["🐎 온라인 윷놀이", "PlayAura", "스쿨잇 (Schoolit)", "인사이트", "AI 도구 가이드", "AI 프롬프트 레시피"]).delete()
    
    print("Seeding data...")
    
    # 1. Seed Insights
    if not Insight.objects.exists():
        Insight.objects.create(
            title="AI 시대, 교사의 역할은 어떻게 변할까?",
            video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            content="지식의 전달자에서 영감의 설계자로.",
            kakio_note="이 영상은 AI 도구를 수업에 녹여내는 구체적인 방법을 제시합니다. 꼭 확인해보세요.",
            tags="#FutureEducation",
            is_featured=True
        )
    
    # 2. Seed All Products/Services
    # Yut Noli
    p_yut = Product.objects.create(
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
    ProductFeature.objects.create(product=p_yut, icon="fa-solid fa-download", title="설치 불필요", description="브라우저에서 바로 실행하세요.")
    ProductFeature.objects.create(product=p_yut, icon="fa-solid fa-users", title="팀 대항전", description="최대 4개 팀까지 참여 가능!")
    ProductFeature.objects.create(product=p_yut, icon="fa-solid fa-dice", title="리얼한 애니메이션", description="윷 던지는 재미가 쏠쏠합니다.")

    # PlayAura
    p_playaura = Product.objects.create(
        title="PlayAura",
        description="전세계 인기 영상 탐험 및 AI 분석 도구",
        price=0,
        is_active=True,
        icon="fa-brands fa-youtube",
        color_theme="red",
        service_type="platform",
        display_order=4,
        external_url="https://motube-woad.vercel.app/",
        image="https://placehold.co/600x400/red/white?text=PlayAura"
    )
    ProductFeature.objects.create(product=p_playaura, icon="fa-solid fa-globe", title="국가별 트렌드", description="전 세계 인기 영상을 한눈에.")
    ProductFeature.objects.create(product=p_playaura, icon="fa-solid fa-magnifying-glass-chart", title="AI 분석", description="영상의 핵심 인사이트를 추출합니다.")

    # Schoolit
    p_schoolit = Product.objects.create(
        title="스쿨잇 (Schoolit)",
        description="선생님과 학생을 위한 스마트 교육 공동체 플랫폼",
        price=0,
        is_active=True,
        icon="fa-solid fa-school",
        color_theme="orange",
        service_type="platform",
        display_order=5,
        external_url="https://schoolit.shop/",
        image="https://placehold.co/600x400/orange/white?text=Schoolit"
    )
    ProductFeature.objects.create(product=p_schoolit, icon="fa-solid fa-handshake", title="교육 연결", description="학교와 교육 업체를 연결합니다.")
    ProductFeature.objects.create(product=p_schoolit, icon="fa-solid fa-robot", title="AI 챗봇 상담", description="채용, 행정 궁금증을 해결하세요.")
    ProductFeature.objects.create(product=p_schoolit, icon="fa-solid fa-comments", title="커뮤니티", description="교육 정보를 나누는 소통의 장.")

    # Core Services
    p_insight = Product.objects.create(
        title="인사이트",
        description="영감 보석함 - AI 시대를 이끄는 선생님의 시선.",
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
    
    p_tools = Product.objects.create(
        title="AI 도구 가이드",
        description="상황별로 딱 맞는 AI 도구를 추천해드려요. 수업 준비부터 행정까지!",
        price=0,
        is_active=True,
        icon="fa-solid fa-robot",
        color_theme="dark",
        service_type="guide",
        card_size="small",
        display_order=7,
        external_url="/tools/",
        image="https://placehold.co/600x400/gray/white?text=AI+Tools"
    )

    p_prompts = Product.objects.create(
        title="AI 프롬프트 레시피",
        description="복사해서 바로 쓰는 검증된 주문서. AI를 200% 활용하세요.",
        price=0,
        is_active=True,
        icon="fa-solid fa-wand-magic-sparkles",
        color_theme="purple",
        service_type="tool",
        card_size="small",
        display_order=8,
        external_url="/prompts/",
        image="https://placehold.co/600x400/purple/white?text=Prompt+Lab"
    )
    
    print("All service data, features, Insights, and Admin account successfully seeded!")

if __name__ == '__main__':
    run()
