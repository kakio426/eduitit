from django.core.management.base import BaseCommand
from products.models import Product, ProductFeature, ServiceManual, ManualSection

class Command(BaseCommand):
    help = 'Ensure 교육 자료실 product exists in database'

    def handle(self, *args, **options):
        # 1. Product 생성 또는 업데이트
        product, created = Product.objects.get_or_create(
            title='교육 자료실',
            defaults={
                'launch_route_name': 'textbooks:main',
                'lead_text': '교과서 기반 학습 자료 모음',
                'description': '국어, 수학, 사회, 과학 교과서 기반의 다양한 교육 자료를 확인하고 학생들에게 배포하세요.',
                'price': 0.00,
                'is_active': True,
                'icon': '📚',
                'color_theme': 'blue',
                'card_size': 'small',
                'service_type': 'tool',
            }
        )
        # 이미 존재하는 경우에도 속성을 갱신할 수 있지만, 기본 defaults 외에는 명시적 업데이트를 생략
        
        self.stdout.write(self.style.SUCCESS(f"Product '{product.title}' ensured."))

        # 2. Product Features 최소 3개 등록
        # 기존 데이터를 초기화하지 않고 필요할 때만 추가
        features_data = [
            {'icon': '📝', 'title': '단원별 자료 제공', 'description': '국어, 수학, 사회, 과학 단원별 맞춤형 자료 제공'},
            {'icon': '📲', 'title': '간편한 학생 배포', 'description': 'QR 코드와 직관적인 URL을 통해 학생들에게 자료를 30초 내에 즉시 배포'},
            {'icon': '🛠️', 'title': '교사 맞춤형 관리', 'description': '수업 계획에 따라 나만의 자료실 세션을 만들고 보관 가능'},
        ]
        
        for idx, feat in enumerate(features_data):
            ProductFeature.objects.get_or_create(
                product=product,
                title=feat['title'],
                defaults={
                    'icon': feat['icon'],
                    'description': feat['description'],
                    'display_order': idx + 1
                }
            )

        self.stdout.write(self.style.SUCCESS("Product features ensured."))

        # 3. Service Manual 자동 생성
        manual, manual_created = ServiceManual.objects.get_or_create(
            product=product,
            defaults={'title': f'{product.title} 사용법', 'is_published': True}
        )

        if manual.sections.count() == 0:
            ManualSection.objects.create(
                manual=manual, 
                title='시작하기', 
                content='원하는 과목과 단원을 선택하고 **자료 검색** 버튼을 눌러 수업에 필요한 자료 목록을 로드하세요.', 
                display_order=1
            )
            ManualSection.objects.create(
                manual=manual, 
                title='주요 기능: 자료 배포', 
                content='자료를 생성한 뒤 **학생들에게 배포하기** 기능을 클릭하면 교실 전면 화면용 QR 코드가 나타납니다. 학생들은 카메라로 즉시 열람이 가능합니다.', 
                display_order=2
            )
            ManualSection.objects.create(
                manual=manual, 
                title='활용 팁', 
                content='매 수업 시작 전, 먼저 자료실 세션을 만들어 두고 모달 창을 닫아두면 수업 진행 시 끊김 없이 학생 접속을 유도할 수 있습니다.', 
                display_order=3
            )
            self.stdout.write(self.style.SUCCESS("Service manual sections created."))
        else:
            self.stdout.write(self.style.SUCCESS("Service manual already has sections."))
        
        self.stdout.write(self.style.SUCCESS("Successfully completed ensure_textbooks."))
