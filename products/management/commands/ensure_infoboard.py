from django.core.management.base import BaseCommand
from products.models import Product, ProductFeature, ServiceManual, ManualSection


class Command(BaseCommand):
    help = 'Ensure InfoBoard product exists in database'

    def handle(self, *args, **options):
        self.stdout.write('=' * 70)
        self.stdout.write('[InfoBoard Product Setup]')
        self.stdout.write('=' * 70)

        product = (
            Product.objects.filter(launch_route_name='infoboard:dashboard').first()
            or Product.objects.filter(title='인포보드').first()
        )

        if product:
            self.stdout.write(f'[!] Found existing InfoBoard product (ID: {product.id})')
            if not product.launch_route_name:
                product.launch_route_name = 'infoboard:dashboard'
                product.save(update_fields=['launch_route_name'])
                self.stdout.write('[OK] Updated launch_route_name')
        else:
            self.stdout.write('[!] InfoBoard product not found, creating...')
            product = Product.objects.create(
                title='인포보드',
                lead_text='자료를 모으고, 정리하고, 공유하세요! 패들릿보다 강력한 정보 모음 보드.',
                description='보드에 링크, 파일, 이미지, 메모를 카드로 추가하고 태그로 정리하세요. '
                            '공유 링크와 QR 코드로 동료 교사나 학생과 간편하게 공유하고, '
                            '학생 카드 제출 기능으로 수업 중 자료 수집에도 활용할 수 있어요.',
                price=0.00,
                is_active=True,
                is_featured=False,
                is_guest_allowed=True,
                icon='📌',
                color_theme='blue',
                card_size='small',
                display_order=25,
                service_type='work',
                external_url='',
                launch_route_name='infoboard:dashboard',
                solve_text='자료 정리와 공유, 한 곳에서 깔끔하게!',
                result_text='정리된 자료 보드',
                time_text='1분',
            )
            self.stdout.write(f'[OK] Created InfoBoard product (ID: {product.id})')

        # Ensure ProductFeatures
        features_data = [
            {
                'icon': '🏷️',
                'title': '태그 기반 교차 정리',
                'description': '하나의 카드에 여러 태그를 붙여 여러 맥락에서 쉽게 찾을 수 있어요.',
            },
            {
                'icon': '📤',
                'title': 'QR·링크·코드 공유',
                'description': 'QR 코드, 링크, 입장 코드 세 가지 방식으로 누구에게든 보드를 공유하세요.',
            },
            {
                'icon': '🧑‍🎓',
                'title': '학생 카드 제출',
                'description': '학생이 QR로 입장해서 자료를 제출할 수 있어요. 수업 중 자료 수집에 딱!',
            },
        ]
        for data in features_data:
            feature, created = ProductFeature.objects.get_or_create(
                product=product,
                title=data['title'],
                defaults=data,
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  [OK] Created feature: {feature.title}'))
            else:
                self.stdout.write(f'  [-] Feature already exists: {feature.title}')

        # Ensure ServiceManual + ManualSections (SIS Rule)
        manual, manual_created = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                'title': '인포보드 사용법',
                'description': '자료를 모으고 정리하고 공유하는 인포보드 활용 가이드',
                'is_published': True,
            },
        )
        if manual_created:
            self.stdout.write(self.style.SUCCESS(f'  [OK] Created ServiceManual'))
        else:
            self.stdout.write(f'  [-] ServiceManual already exists')

        if manual.sections.count() == 0:
            ManualSection.objects.create(
                manual=manual,
                title='시작하기',
                content=(
                    '1. 인포보드에 들어가면 "새 보드" 버튼을 눌러 첫 보드를 만드세요.\n'
                    '2. 보드 이름, 아이콘, 색상을 선택하고 "만들기"를 누르세요.\n'
                    '3. 보드 안에서 "카드 추가"를 눌러 링크, 파일, 이미지, 메모를 추가하세요.'
                ),
                display_order=1,
            )
            ManualSection.objects.create(
                manual=manual,
                title='주요 기능',
                content=(
                    '**태그**: 카드에 태그를 붙이면 여러 보드를 가로질러 검색할 수 있어요.\n'
                    '**공유**: 보드 상세에서 "공유" 버튼을 누르면 링크·QR·코드로 공유 가능!\n'
                    '**학생 제출**: 공유 시 "카드 제출 가능"을 선택하면 학생이 카드를 제출할 수 있어요.\n'
                    '**검색**: Ctrl+K로 모든 보드와 카드를 한 번에 검색하세요.'
                ),
                display_order=2,
            )
            ManualSection.objects.create(
                manual=manual,
                title='활용 팁',
                content=(
                    '- 수업 자료 보드: 교과별로 보드를 만들고 단원 태그를 활용하세요.\n'
                    '- 조별 발표 모음: 학생 제출을 켜면 조별로 자료를 한 보드에 모을 수 있어요.\n'
                    '- 교사 공유 보드: 동료 교사에게 링크를 보내 유용한 자료를 공유하세요.'
                ),
                display_order=3,
            )
            self.stdout.write(self.style.SUCCESS(f'  [OK] Created 3 ManualSections'))
        else:
            self.stdout.write(f'  [-] ManualSections already exist ({manual.sections.count()})')

        self.stdout.write('=' * 70)
        self.stdout.write('[OK] Done!')
