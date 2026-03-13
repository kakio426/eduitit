from django.core.management.base import BaseCommand
from products.models import Product, ProductFeature


class Command(BaseCommand):
    help = 'Ensure StudentMBTI product exists in database'

    def handle(self, *args, **options):
        self.stdout.write('=' * 70)
        self.stdout.write('[StudentMBTI Product Setup]')
        self.stdout.write('=' * 70)

        product = Product.objects.filter(title='우리반BTI').first() or \
                  Product.objects.filter(title='우리반 캐릭터 친구 찾기').first() or \
                  Product.objects.filter(title__icontains='studentmbti').first()

        if product:
            self.stdout.write(f'[!] Found existing StudentMBTI product (ID: {product.id})')
            needs_update = False
            default_lead_text = '우리 반 친구들은 어떤 동물 캐릭터일까? QR 코드 하나로 시작하는 재미있는 성격 탐험! 🐾'
            default_description = '선생님이 세션을 만들고 QR코드를 공유하면, 학생들은 회원가입 없이 바로 참여할 수 있어요. 재미있는 질문에 답하면 나와 닮은 동물 캐릭터를 알려줍니다. 16가지 동물 캐릭터로 학생들의 성격 특성을 파악하고, 학급 운영에 활용해보세요!'
            if product.title != '우리반BTI':
                product.title = '우리반BTI'
                needs_update = True
            if not (product.lead_text or '').strip():
                product.lead_text = default_lead_text
                needs_update = True
            if not (product.description or '').strip():
                product.description = default_description
                needs_update = True
            if needs_update:
                product.save()
                self.stdout.write('[OK] Updated existing product settings')
            else:
                self.stdout.write('[OK] Product already has correct settings')
        else:
            self.stdout.write('[!] StudentMBTI product not found, creating...')

            product = Product.objects.create(
                title='우리반BTI',
                lead_text='우리 반 친구들은 어떤 동물 캐릭터일까? QR 코드 하나로 시작하는 재미있는 성격 탐험! 🐾',
                description='선생님이 세션을 만들고 QR코드를 공유하면, 학생들은 회원가입 없이 바로 참여할 수 있어요. 재미있는 질문에 답하면 나와 닮은 동물 캐릭터를 알려줍니다. 16가지 동물 캐릭터로 학생들의 성격 특성을 파악하고, 학급 운영에 활용해보세요!',
                price=0.00,
                is_active=True,
                is_featured=False,
                is_guest_allowed=True,
                icon='🐾',
                color_theme='green',
                card_size='small',
                display_order=15,
                service_type='counsel',
                external_url='',
            )
            self.stdout.write(f'[OK] Created StudentMBTI product (ID: {product.id})')

        # Ensure correct settings for existing product as well
        if product.service_type != 'counsel':
            product.service_type = 'counsel'
            product.save()
            self.stdout.write('[OK] Updated service_type to counsel')

        # Ensure ProductFeatures exist
        # product.features.all().delete()  <-- DO NOT DELETE

        features_data = [
            {
                'icon': '📱',
                'title': 'QR코드로 간편 참여',
                'description': '학생들은 회원가입 없이 QR코드 스캔만으로 바로 참여할 수 있어요. 이름만 입력하면 끝!'
            },
            {
                'icon': '🐾',
                'title': '16가지 동물 캐릭터',
                'description': '거북이, 강아지, 판다, 돌고래 등 귀여운 동물 캐릭터로 성격 유형을 재미있게 알려줍니다.'
            },
            {
                'icon': '📊',
                'title': '교사용 실시간 대시보드',
                'description': '학생들의 참여 현황과 결과를 실시간으로 확인하고, 엑셀로 내보내기까지 한번에!'
            },
        ]

        for feature_data in features_data:
            feature, created = ProductFeature.objects.get_or_create(
                product=product,
                title=feature_data['title'],
                defaults=feature_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  [OK] Created feature: {feature.title}'))
            else:
                self.stdout.write(f'  [-] Feature already exists: {feature.title}')
        self.stdout.write('=' * 70)
        self.stdout.write('[OK] Done!')
