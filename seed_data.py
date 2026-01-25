import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

def run():
    from products.models import Product, ProductFeature
    from insights.models import Insight
    from django.contrib.auth.models import User

    # Create superuser if it doesn't exist
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'admin1234')
        print("Superuser 'admin' created successfully!")

    # Force re-seeding for clean state
    print("Cleaning database...")
    Product.objects.all().delete()
    ProductFeature.objects.all().delete()
    print("Database cleaned.")
    
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

    # 1. 반짝반짝 우리반 알림판 (구 DutyTicker)
    p_duty = Product.objects.create(
        title="반짝반짝 우리반 알림판",
        lead_text="선생님, 저 지금 뭐해요? 우리 반 아이들이 할 일을 잊지 않도록 화면으로 챙겨주세요.",
        description="\"선생님, 저 청소 당번인 거 깜빡했어요!\" 이런 말, 이제 그만 듣고 싶으시죠? 교실 TV에 '반짝반짝 우리반 알림판'을 띄워두세요. 자신의 이름과 해야 할 일이 화면에 계속 보이니, 아이들이 선생님 잔소리 없이도 스스로 할 일을 기억하고 실천합니다.",
        price=0,
        is_active=True,
        icon="fa-solid fa-users-gear",
        color_theme="purple",
        service_type="tool",
        display_order=1,
        external_url="/products/dutyticker/",
        image="https://placehold.co/600x400/purple/white?text=DutyTicker"
    )
    ProductFeature.objects.create(product=p_duty, icon="fa-solid fa-tv", title="한눈에 보는 역할표", description="현재 누가 어떤 역할을 맡고 있는지 큼직한 화면으로 보여주어 아이들이 잊지 않습니다.")
    ProductFeature.objects.create(product=p_duty, icon="fa-solid fa-user-check", title="스스로 챙기는 책임감", description="자신의 이름이 화면에 떠 있으니 선생님의 지시 없이도 스스로 당번 활동을 시작합니다.")
    ProductFeature.objects.create(product=p_duty, icon="fa-solid fa-stopwatch", title="활동 집중 타이머", description="청소 시간이나 쉬는 시간 등 활동 시간을 화면에 함께 띄워 효율적인 시간 관리를 돕습니다.")

    # 2. 왁자지껄 교실 윷놀이 (구 Yut Game)
    p_yut = Product.objects.create(
        title="왁자지껄 교실 윷놀이",
        lead_text="준비물도 뒷정리도 필요 없어요. 커다란 화면 속에서 다 함께 즐기는 우리 전통 놀이!",
        description="창의적 체험활동 시간이나 비 오는 날 체육 시간, 무엇을 할지 고민이신가요? 준비물 없이 화면 하나로 즐기는 '왁자지껄 교실 윷놀이'로 우리 반의 단합력을 높여보세요. 아이들의 환호성으로 교실이 가득 찰 거예요.",
        price=0,
        is_active=True,
        is_featured=True,
        icon="🎲",
        color_theme="green",
        service_type="game",
        display_order=2,
        external_url="/products/yut/",
        image="https://placehold.co/600x400/green/white?text=Yut+Noli"
    )
    ProductFeature.objects.create(product=p_yut, icon="fa-solid fa-people-group", title="팀 대항전 모드", description="모둠별로 팀을 나누어 박진감 넘치는 대결을 펼칠 수 있습니다.")
    ProductFeature.objects.create(product=p_yut, icon="fa-solid fa-hand-back-fist", title="리얼한 윷 던지기", description="터치 한 번으로 윷을 던지는 쫄깃한 긴장감을 그대로 구현했습니다.")
    ProductFeature.objects.create(product=p_yut, icon="fa-solid fa-robot", title="자동 말 이동 시스템", description="복잡한 윷판 규칙을 몰라도 AI가 알아서 말을 놓아줍니다.")

    # 3. 토닥토닥 선생님 운세 (구 Teacher Saju)
    p_fortune = Product.objects.create(
        title="토닥토닥 선생님 운세",
        lead_text="많이 힘드셨죠? 지친 선생님의 하루에 작은 위로와 웃음을 드려요.",
        description="힘든 학급 붕괴의 위기 속에서도 웃음을 잃지 마세요. 재미로 보는 '토닥토닥 선생님 운세'가 선생님의 지친 하루에 작은 위로와 활력소가 되어드릴 것입니다. (물론, 맹신은 금물입니다!)",
        price=0,
        is_active=True,
        icon="🔮",
        color_theme="blue",
        service_type="tool",
        display_order=3,
        external_url="/fortune/",
        image="https://placehold.co/600x400/blue/white?text=Fortune"
    )
    ProductFeature.objects.create(product=p_fortune, icon="fa-solid fa-heart-pulse", title="오늘의 생존 지수", description="출근길, 오늘의 학급 평화가 지켜질지 미리 확인해보세요.")
    ProductFeature.objects.create(product=p_fortune, icon="fa-solid fa-gift", title="행운의 아이템", description="오늘 나를 지켜줄 소지품이나 간식을 추천해 드립니다.")
    ProductFeature.objects.create(product=p_fortune, icon="fa-solid fa-handshake", title="동료 교사 궁합", description="옆 반 선생님과의 케미를 재미로 알아보는 기능도 제공합니다.")

    # 4. 가뿐하게 서명 톡 (구 Signatures)
    p_signatures = Product.objects.create(
        title="가뿐하게 서명 톡",
        lead_text="바쁜 쉬는 시간, 결재판 들고 교무실 내려갈 필요 없어요. 내 자리에서 링크 하나로 서명 끝!",
        description="\"연수 때마다 종이 명단 돌리고 사인받기 귀찮으셨죠?\" 이제 종이 낭비 없이 태블릿이나 링크 공유로 간편하게 서명을 받으세요. 연수가 끝나면 참석자 명단이 실시간으로 취합되고, 서명이 포함된 PDF 결과 보고서까지 자동으로 생성됩니다.",
        price=0,
        is_active=True,
        icon="🖋️",
        color_theme="orange",
        service_type="tool",
        display_order=4,
        external_url="/signatures/",
        image="https://placehold.co/600x400/orange/white?text=Signatures"
    )
    ProductFeature.objects.create(product=p_signatures, icon="fa-solid fa-qrcode", title="간편한 서명 배부", description="연수 장소에 QR코드를 띄우거나 링크를 공유하여 참석자들이 즉시 서명할 수 있습니다.")
    ProductFeature.objects.create(product=p_signatures, icon="fa-solid fa-users", title="실시간 참석 확인", description="누가 서명을 완료했는지 대시보드에서 실시간으로 확인하고 미참석자를 관리하세요.")
    ProductFeature.objects.create(product=p_signatures, icon="fa-solid fa-file-pdf", title="PDF 결과 보고서", description="취합된 서명은 결재 문서에 바로 첨부할 수 있는 깔끔한 PDF 양식으로 자동 변환됩니다.")

    # 其他 기존 서비스들 (유지)
    # 패들릿 AI 봇 -> 궁금해? 패들릿 봇
    p_padlet = Product.objects.create(
        title="궁금해? 패들릿 봇",
        lead_text="패들릿 주소만 쏙 넣으세요. 그 안의 모든 내용을 읽고, 어떤 질문이든 찰떡같이 찾아 답변해 드려요.",
        description="수업 자료를 패들릿에 올리셨나요? 이제 그 자료가 AI 챗봇이 됩니다. 학생들이 '선생님, 이거 어디 있어요?'라고 물으면 AI가 대신 찾아서 답변해줍니다. 패들릿 URL만 연결하면 게시물 내용을 자동으로 학습합니다. 선생님은 자료만 올리고, 나머지는 AI에게 맡기세요.",
        price=0,
        is_active=True,
        icon="📋",
        color_theme="blue",
        service_type="tool",
        display_order=5,
        external_url="/padlet/",
        image="https://placehold.co/600x400/blue/white?text=Padlet+AI"
    )
    ProductFeature.objects.create(product=p_padlet, icon="fa-solid fa-robot", title="RAG 기반 AI 채팅", description="업로드한 문서 내용을 기반으로 정확한 답변을 생성합니다. 헛소리 없이 자료에 있는 내용만 답변합니다.")
    ProductFeature.objects.create(product=p_padlet, icon="fa-solid fa-link", title="패들릿 자동 연동", description="패들릿 URL만 붙여넣으면 게시물 내용을 자동으로 가져와 학습합니다. API 키만 있으면 실시간 동기화도 가능합니다.")
    ProductFeature.objects.create(product=p_padlet, icon="fa-solid fa-file-csv", title="다양한 파일 지원", description="CSV, PDF, TXT 등 다양한 형식의 문서를 업로드하여 AI 지식베이스를 구축할 수 있습니다.")

    # AI 미술 수업
    p_artclass = Product.objects.create(
        title="몽글몽글 미술 수업",
        lead_text="유튜브 미술 영상을 분석해서 단계별 수업 안내를 자동 생성하는 스마트 도우미",
        description="'이 부분에서 잠깐 멈추고 따라 그려보세요'라고 일일이 설명하기 힘드셨죠? 이제 유튜브 미술 영상 URL만 넣으면 AI가 영상을 분석하여 학생들이 따라하기 좋은 단계별 안내를 자동으로 만들어줍니다. 교실 TV에 띄워놓고 학생들과 함께 차근차근 작품을 완성해보세요.",
        price=0,
        is_active=True,
        icon="🎨",
        color_theme="purple",
        service_type="tool",
        display_order=6,
        external_url="/artclass/",
        image="https://placehold.co/600x400/purple/white?text=AI+Art+Class"
    )
    ProductFeature.objects.create(product=p_artclass, icon="fa-solid fa-wand-magic-sparkles", title="AI 단계별 안내 생성", description="유튜브 영상의 자막과 내용을 분석하여 학생 눈높이에 맞는 단계별 수업 가이드를 자동 생성합니다.")
    ProductFeature.objects.create(product=p_artclass, icon="fa-solid fa-tv", title="교실 수업 모드", description="생성된 단계를 교실 TV에 띄워놓고 버튼 하나로 다음 단계로 넘어가며 수업을 진행할 수 있습니다.")
    ProductFeature.objects.create(product=p_artclass, icon="fa-solid fa-clock", title="타이머 연동", description="각 단계별 작업 시간을 설정하여 학생들이 충분히 따라할 시간을 확보할 수 있습니다.")

    # AutoArticle -> 글솜씨 뚝딱! 소식지
    p_auto = Product.objects.create(
        title="글솜씨 뚝딱! 소식지",
        lead_text="글 쓰는 게 막막할 때 키워드만 톡! 학부모님이 감동하는 멋진 소식지를 선사해요.",
        description="복잡한 기사 작성을 버튼 클릭 몇 번으로 해결하세요. 수업 소식, 학교 행사 등을 멋진 기사 형태로 변환하여 학부모님과 공유할 수 있습니다.",
        price=0,
        is_active=True,
        icon="fa-solid fa-robot",
        color_theme="purple",
        service_type="tool",
        display_order=7,
        external_url="/autoarticle/",
        image="https://placehold.co/600x400/purple/white?text=AI+Article"
    )
    ProductFeature.objects.create(product=p_auto, icon="fa-solid fa-wand-magic-sparkles", title="AI 자동 글쓰기", description="주제만 입력하면 Gemini AI가 흐름에 맞는 전문적인 글을 생성합니다.")
    ProductFeature.objects.create(product=p_auto, icon="fa-solid fa-image", title="이미지 결합", description="관련 이미지를 업로드하면 기사 본문에 적절히 배치하여 가독성을 높입니다.")
    ProductFeature.objects.create(product=p_auto, icon="fa-solid fa-file-export", title="다양한 내보내기", description="생성된 결과물을 HTML 또는 PPT 형식으로 변환하여 바로 활용하세요.")

    # PlayAura -> 유튜브 탈알고리즘
    p_playaura = Product.objects.create(
        title="유튜브 탈알고리즘",
        lead_text="내 피드에 갇힌 시야를 넓혀보세요. 추천 영상 너머, 전 세계 친구들이 진짜로 보고 있는 세상을 만나요.",
        description="대형 언론사나 유명 유튜버가 아닌, 사람들의 진심 어린 사랑을 받고 있는 숨은 보석 같은 유튜브 채널을 매일매일 발견하세요. 알고리즘에 갇히지 않고 새로운 콘텐츠를 만나는 특별한 경험을 선사합니다.",
        price=0,
        is_active=True,
        icon="fa-brands fa-youtube",
        color_theme="red",
        service_type="platform",
        display_order=8,
        external_url="https://motube-woad.vercel.app/",
        image="https://placehold.co/600x400/red/white?text=PlayAura"
    )
    ProductFeature.objects.create(product=p_playaura, icon="fa-solid fa-gem", title="숨은 보석 발굴", description="대형 채널을 제외하고 진짜 사랑받는 중소형 크리에이터들의 채널을 매일 추천합니다.")
    ProductFeature.objects.create(product=p_playaura, icon="fa-solid fa-heart", title="진심 어린 큐레이션", description="조회수가 아닌 진정성으로 선별된 채널들을 통해 새로운 영감을 얻으세요.")

    # Schoolit (유지 또는 변경?) -> Schoolit은 업체명이므로 유지하는 것이 맞아 보임.
    p_schoolit = Product.objects.create(
        title="학교 통합 지원 스쿨잇",
        lead_text="복잡한 채용 업무와 업체 선정은 그만! AI가 학교에 딱 맞는 선생님은 물론, 신뢰할 수 있는 학교 행사 업체까지 한곳에서 연결해 드립니다.",
        description="\"갑자기 대체 교사는 어디서 구하지?\", \"믿을만한 체험학습 업체는 어디일까?\" 매번 반복되는 채용난과 업체 선정 스트레스에서 벗어나세요. 스쿨잇은 학교의 행정 부담을 획기적으로 줄여주기 위해 탄생했습니다. AI를 통한 스마트한 채용 상담부터 검증된 행사 업체 매칭까지, 학교 운영에 필요한 모든 연결을 이 한 곳에서 쉽고 빠르게 해결할 수 있습니다.",
        price=0,
        is_active=True,
        icon="fa-solid fa-school",
        color_theme="orange",
        service_type="platform",
        display_order=9,
        external_url="https://schoolit.shop/",
        image="https://placehold.co/600x400/orange/white?text=Schoolit"
    )
    ProductFeature.objects.create(product=p_schoolit, icon="fa-solid fa-file-pen", title="3분 간편 공고", description="과목, 시간 등 조건만 입력하면 스쿨잇이 복잡한 채용 공고를 뚝딱 완성합니다.")
    ProductFeature.objects.create(product=p_schoolit, icon="fa-solid fa-robot", title="AI 행정 지원", description="채용 과정이나 행정 절차에 대해 궁금한 점이 있다면 24시간 대기 중인 AI 비서에게 바로 물어보고 해결하세요.")
    ProductFeature.objects.create(product=p_schoolit, icon="fa-solid fa-magnifying-glass", title="행사 업체 일괄 검색", description="체험학습, 진로체험활동, 스포츠데이 등 학교 행사 업체를 여기저기 연락할 필요 없이 스쿨잇에서 한 번에 찾아볼 수 있습니다.")

    # Small/Wide Cards
    Product.objects.create(
        title="인사이트",
        lead_text="AI 시대를 이끄는 선생님들을 위한 보석 같은 영감들을 모았습니다.",
        description="영감 보석함 - 교육의 미래를 고민하는 선생님들과 함께 나누고 싶은 깊이 있는 통찰력을 제공합니다.",
        price=0,
        is_active=True,
        icon="fa-solid fa-gem",
        color_theme="purple",
        service_type="library",
        card_size="small",
        display_order=10,
        external_url="/insights/",
        image="https://placehold.co/600x400/purple/white?text=Insights"
    )
    
    Product.objects.create(
        title="AI 도구 가이드",
        lead_text="상황별로 딱 맞는 AI 도구를 추천해드려요.",
        description="수업 준비부터 생활 지도까지! 복잡한 AI 툴들 사이에서 선생님께 꼭 필요한 것만 골라 사용법과 함께 안내합니다.",
        price=0,
        is_active=True,
        icon="fa-solid fa-robot",
        color_theme="dark",
        service_type="guide",
        card_size="small",
        display_order=11,
        external_url="/tools/",
        image="https://placehold.co/600x400/gray/white?text=AI+Tools"
    )

    Product.objects.create(
        title="AI 프롬프트 레시피",
        lead_text="복사해서 바로 쓰는 검증된 AI 주문서.",
        description="AI 전문가의 노하우가 담긴 프롬프트를 내 것으로! 시행착오 없이 바로 수업에 적용 가능한 강력한 프롬프트들을 제공합니다.",
        price=0,
        is_active=True,
        icon="fa-solid fa-wand-magic-sparkles",
        color_theme="purple",
        service_type="tool",
        card_size="wide",
        display_order=12,
        external_url="/prompts/",
        image="https://placehold.co/600x400/purple/white?text=Prompt+Lab"
    )
    
    print("All service data, features, Insights, and Admin account successfully seeded!")

if __name__ == '__main__':
    run()
