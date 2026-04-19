from django.core.management.base import BaseCommand
from products.models import Product, ProductFeature


class Command(BaseCommand):
    help = 'Ensure Collect product exists in database'

    def handle(self, *args, **options):
        self.stdout.write('=' * 70)
        self.stdout.write('[Collect Product Setup]')
        self.stdout.write('=' * 70)

        product = (
            Product.objects.filter(launch_route_name='collect:landing').first()
            or Product.objects.filter(title__icontains='잇티수합').first()
            or Product.objects.filter(title__icontains='간편 수합').first()
            or Product.objects.filter(title__icontains='collect').first()
        )

        if product:
            self.stdout.write(f'[!] Found existing Collect product (ID: {product.id})')
            changed_fields = []
            if product.title != '잇티수합':
                product.title = '잇티수합'
                changed_fields.append('title')
            if product.launch_route_name != 'collect:landing':
                product.launch_route_name = 'collect:landing'
                changed_fields.append('launch_route_name')
            if changed_fields:
                product.save(update_fields=changed_fields)
                self.stdout.write(f"[OK] Updated existing product settings: {', '.join(changed_fields)}")
            else:
                self.stdout.write('[OK] Product already has correct settings')
        else:
            self.stdout.write('[!] Collect product not found, creating...')

            product = Product.objects.create(
                title='잇티수합',
                lead_text='QR 코드 하나로 파일·링크·텍스트·선택형 응답을 간편하게 수합하세요!',
                description='여러 선생님으로부터 파일이나 정보를 수합해야 할 때, 메신저로 하나하나 받지 마세요. 수합 요청을 만들고 QR/코드를 공유하면, 참여자들은 회원가입 없이 파일·링크·텍스트·선택형 응답을 제출합니다. 한 화면에서 모든 제출물을 확인하고 다운로드하세요!',
                price=0.00,
                is_active=True,
                is_featured=False,
                is_guest_allowed=True,
                icon='📋',
                color_theme='green',
                card_size='small',
                display_order=20,
                service_type='work',
                external_url='',
                launch_route_name='collect:landing',
                solve_text='문서와 의견 수합, 번거로운 일은 이제 저에게 맡겨주세요!',
                result_text='정리된 제출 목록',
                time_text='3분',
            )
            self.stdout.write(f'[OK] Created Collect product (ID: {product.id})')
        # Ensure ProductFeatures exist
        # product.features.all().delete()

        features_data = [
            {
                'icon': '📱',
                'title': 'QR 코드로 간편 제출',
                'description': '참여자들은 회원가입 없이 QR코드 스캔이나 입장코드 입력만으로 바로 제출할 수 있어요.'
            },
            {
                'icon': '📁',
                'title': '파일·링크·텍스트·선택형 수합',
                'description': '한글, 엑셀, PDF 등 파일은 물론 구글드라이브 링크, 텍스트, 선택형 응답까지 한 곳에서 수합합니다.'
            },
            {
                'icon': '⬇️',
                'title': '일괄 다운로드 & CSV',
                'description': '제출된 파일을 ZIP으로 한번에 다운로드하고, 제출 목록을 CSV로 내보낼 수 있어요.'
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
