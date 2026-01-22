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
        Product.objects.filter(title__in=["🐎 온라인 윷놀이", "PlayAura", "스쿨잇 (Schoolit)", "인사이트", "AI 도구 가이드", "AI 프롬프트 레시피", "기사 자동 생성"]).delete()
    
    print("Seeding data...")
    
    # 1. Seed Insights
    if not Insight.objects.exists():
        Insight.objects.create(
            title="AI 시대를 맞이하는 교사의 새로운 전문성",
            video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            content="이제 교사는 지식 전달자가 아닌 영감의 설계자가 되어야 합니다.",
            kakio_note="AI 도구를 어떻게 수업에 녹여낼지 고민되신다면 이 영상을 꼭 확인해보세요.",
            tags="#AI교육 #미래교육",
            is_featured=True
        )
    
    # 2. Seed All Products/Services
    # Yut Noli
    p_yut = Product.objects.create(
        title="🐎 온라인 윷놀이",
        description="설치 없이 브라우저에서 바로 즐기는 학급 대항전 필수 아이템! 리얼한 물리 엔진으로 실제 윷을 던지는 손맛을 느껴보세요.",
        price=0,
        is_active=True,
        is_featured=True,
        icon="🎲",
        color_theme="green",
        service_type="game",
        display_order=1,
        image="https://placehold.co/600x400/green/white?text=Yut+Noli"
    )
    ProductFeature.objects.create(product=p_yut, icon="fa-solid fa-bolt", title="즉시 실행", description="별도의 프로그램 설치 없이 클릭 한 번으로 시작합니다.")
    ProductFeature.objects.create(product=p_yut, icon="fa-solid fa-users", title="멀티플레이", description="최대 4개 팀까지 참여하여 긴장감 넘치는 학급 대항전을 즐기세요.")
    ProductFeature.objects.create(product=p_yut, icon="fa-solid fa-dice", title="리얼 물리엔진", description="윷의 회전과 충돌을 정밀하게 계산하는 물리 엔진이 적용되었습니다.")


    # AutoArticle
    p_auto = Product.objects.create(
        title="기사 자동 생성",
        description="몇 가지 키워드와 이미지만으로 전문적인 교육 뉴스레터나 정보를 담은 기사를 AI가 뚝딱 만들어드립니다.",
        price=0,
        is_active=True,
        icon="fa-solid fa-robot",
        color_theme="purple",
        service_type="tool",
        display_order=3,
        external_url="/autoarticle/",
        image="https://placehold.co/600x400/purple/white?text=AI+Article"
    )
    ProductFeature.objects.create(product=p_auto, icon="fa-solid fa-wand-magic-sparkles", title="AI 자동 글쓰기", description="주제만 입력하면 Gemini AI가 흐름에 맞는 전문적인 글을 생성합니다.")
    ProductFeature.objects.create(product=p_auto, icon="fa-solid fa-image", title="이미지 결합", description="관련 이미지를 업로드하면 기사 본문에 적절히 배치하여 가독성을 높입니다.")
    ProductFeature.objects.create(product=p_auto, icon="fa-solid fa-file-export", title="다양한 내보내기", description="생성된 결과물을 HTML 또는 PPT 형식으로 변환하여 바로 활용하세요.")

    # PlayAura
    p_playaura = Product.objects.create(
        title="PlayAura",
        description="전 세계 인기 유튜브 영상을 국가별 트렌드로 탐험하고, AI를 통해 영상의 핵심 인사이트를 요약받으세요.",
        price=0,
        is_active=True,
        icon="fa-brands fa-youtube",
        color_theme="red",
        service_type="platform",
        display_order=4,
        external_url="https://motube-woad.vercel.app/",
        image="https://placehold.co/600x400/red/white?text=PlayAura"
    )
    ProductFeature.objects.create(product=p_playaura, icon="fa-solid fa-globe", title="글로벌 트렌드", description="미국, 영국, 일본 등 각국의 유튜브 인기 순위를 실시간으로 확인합니다.")
    ProductFeature.objects.create(product=p_playaura, icon="fa-solid fa-magnifying-glass-chart", title="AI 영상 요약", description="긴 영상도 핵심만 골라 요약해주는 스마트한 분석 도구를 경험하세요.")

    # Schoolit
    p_schoolit = Product.objects.create(
        title="스쿨잇 (Schoolit)",
        description="선생님과 학생을 위한 스마트 교육 공동체 플랫폼. 교육 업체 연결부터 AI 챗봇 상담까지 교육의 모든 것을 담았습니다.",
        price=0,
        is_active=True,
        icon="fa-solid fa-school",
        color_theme="orange",
        service_type="platform",
        display_order=5,
        external_url="https://schoolit.shop/",
        image="https://placehold.co/600x400/orange/white?text=Schoolit"
    )
    ProductFeature.objects.create(product=p_schoolit, icon="fa-solid fa-comments", title="교육 커뮤니티", description="선생님들만의 진솔한 정보 공유와 소통의 장을 제공합니다.")
    ProductFeature.objects.create(product=p_schoolit, icon="fa-solid fa-robot", title="AI 행정 비서", description="복잡한 학사 일정이나 행정 절차를 챗봇이 친절하게 안내해드립니다.")

    # Core Services (Internal Links)
    p_insight = Product.objects.create(
        title="인사이트",
        description="영감 보석함 - AI 시대를 이끄는 선생님들을 위한 보석 같은 영감들을 모았습니다.",
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
        description="상황별로 딱 맞는 AI 도구를 추천해드려요. 수업 준비부터 생활 지도까지 해결하세요.",
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
        description="복사해서 바로 쓰는 검증된 주문서. AI 전문가의 프롬프트를 내 것으로 만드세요.",
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
    
    print("All service data, features, Insights, and Admin account successfully seeded!")

if __name__ == '__main__':
    run()
