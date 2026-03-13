
from django.core.management.base import BaseCommand
from products.models import Product, ProductFeature


class Command(BaseCommand):
    help = 'Ensure Chess product exists in database'

    def handle(self, *args, **options):
        self.stdout.write('=' * 70)
        self.stdout.write('[Chess Product Setup]')
        self.stdout.write('=' * 70)

        # Check if product exists
        chess = Product.objects.filter(title__icontains='체스').first()

        if chess:
            self.stdout.write(f'[!] Found existing Chess product (ID: {chess.id})')
            # Update settings
            chess.title = '두뇌 풀가동! 교실 체스'
            chess.external_url = ''
            chess.service_type = 'game'
            chess.save()
            self.stdout.write('[OK] Updated existing product settings')
        else:
            self.stdout.write('[!] Chess product not found, creating...')

            # Create new product
            chess = Product.objects.create(
                title='두뇌 풀가동! 교실 체스',
                lead_text='준비물 NO! 설치 NO! 브라우저만 있으면 세계 최강 AI와 체스 한판 어때요? ♟️',
                description='선생님, 비 오는 날이나 창체 시간에 아이들과 체스 한판 어떠신가요? "두뇌 풀가동! 교실 체스"는 별도의 설치나 가입 없이 바로 즐길 수 있는 체스 게임입니다. 친구와 함께하는 로컬 대전은 물론, 세계 최강 AI Stockfish와 실력을 겨뤄볼 수 있습니다. 규칙을 몰라도 걱정 마세요! 상세한 가이드가 함께 제공됩니다.',
                price=0.00,
                is_active=True,
                is_featured=False,
                icon='♟️',
                color_theme='dark',
                card_size='small',
                display_order=14,
                service_type='game',
                external_url='',
            )
            self.stdout.write(f'[OK] Created Chess product (ID: {chess.id})')

        # Ensure ProductFeatures exist
        # chess.features.all().delete()

        # Create features
        features_data = [
            {
                'icon': '🤖',
                'title': '무료 AI 대전 (Stockfish)',
                'description': '세계 최강급 AI 엔진 Stockfish.js를 탑재했습니다. 4단계 난이도(초급~최강)로 자신의 실력에 맞춰 도전해보세요.'
            },
            {
                'icon': '🤝',
                'title': '1대1 로컬 대전',
                'description': '친구와 나란히 앉아 하나의 화면으로 즐기는 클래식한 로컬 대전 모드를 지원합니다.'
            },
            {
                'icon': '📜',
                'title': '왕초보 가이드',
                'description': '기초적인 말의 이동부터 캐슬링, 앙파상 같은 특수 규칙까지! 초보자도 금방 배울 수 있는 상세한 가이드를 제공합니다.'
            }
        ]

        for feature_data in features_data:
            feature, created = ProductFeature.objects.get_or_create(
                product=chess,
                title=feature_data['title'],
                defaults=feature_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  [OK] Created feature: {feature.title}'))
            else:
                self.stdout.write(f'  [-] Feature already exists: {feature.title}')
        self.stdout.write('=' * 70)
        self.stdout.write('[OK] Done!')
