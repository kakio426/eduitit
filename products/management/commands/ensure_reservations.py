from django.core.management.base import BaseCommand
from products.models import Product, ProductFeature

class Command(BaseCommand):
    help = 'Ensure Reservations product exists in database'

    def handle(self, *args, **options):
        self.stdout.write('=' * 70)
        self.stdout.write(self.style.WARNING('[Reservations Product Setup]'))
        self.stdout.write('=' * 70)

        title = '학교 예약 시스템'
        
        # Check if product exists
        product = Product.objects.filter(title=title).first()

        if product:
            self.stdout.write(self.style.WARNING(f'[!] Found existing Reservations product (ID: {product.id})'))
            
            # Update fields that are safe to update (Code-driven)
            product.lead_text = '복잡한 특별실 예약, 이제 클릭 한 번으로!'
            product.description = '과학실, 컴퓨터실 등 특별실 예약을 실시간으로 확인하고 간편하게 신청하세요. 선생님들의 업무가 줄어듭니다.'
            product.icon = '🏫'
            product.color_theme = 'purple'
            product.card_size = 'small'
            product.is_guest_allowed = True # Students/Guests use it
            
            # CRITICAL: Do NOT overwrite Admin-managed fields
            # - service_type
            # - display_order
            # - is_active (Let admin control visibility)
            
            # Ensure external_url is empty for internal app
            if product.external_url:
                product.external_url = ''
            
            product.save()
            self.stdout.write(self.style.SUCCESS('[OK] Updated Reservations product (Skipped Admin-managed fields)'))

        else:
            self.stdout.write(self.style.WARNING('[!] Reservations product not found, creating...'))

            # Create new product with defaults
            product = Product.objects.create(
                title=title,
                lead_text='복잡한 특별실 예약, 이제 클릭 한 번으로!',
                description='과학실, 컴퓨터실 등 특별실 예약을 실시간으로 확인하고 간편하게 신청하세요. 선생님들의 업무가 줄어듭니다.',
                price=0.00,
                is_active=True,
                is_featured=False,
                is_guest_allowed=True,
                icon='🏫',
                color_theme='purple',
                card_size='small',
                display_order=99, # Default order
                service_type='classroom', # Default service type
                external_url='',
            )
            self.stdout.write(self.style.SUCCESS(f'[OK] Created Reservations product (ID: {product.id})'))

        # Ensure ProductFeatures exist
        self.stdout.write('')
        self.stdout.write('[Ensuring Product Features...]')

        features_data = [
            {
                'icon': '⚡',
                'title': '실시간 예약 현황',
                'description': '다른 반의 예약 현황을 실시간으로 확인하고 중복 없이 신청하세요.'
            },
            {
                'icon': '📱',
                'title': '모바일 최적화',
                'description': 'PC는 물론 모바일에서도 편리하게 시간표를 확인하고 예약할 수 있습니다.'
            },
            {
                'icon': '🛡️',
                'title': '관리자 편의성',
                'description': '고정 수업 설정, 행사 기간 블랙아웃 등 관리자 기능으로 유연하게 운영하세요.'
            }
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
