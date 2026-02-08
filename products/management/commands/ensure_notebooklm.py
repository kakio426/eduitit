from django.core.management.base import BaseCommand
from products.models import Product, ProductFeature

class Command(BaseCommand):
    help = 'Ensure NotebookLM (Teacher Encyclopedia) product exists in database'

    def handle(self, *args, **options):
        # 1. Product creation (SIS 1, 6.1)
        product, created = Product.objects.get_or_create(
            title='교사 백과사전',
            defaults={
                'lead_text': 'AI와 함께하는 교육 매뉴얼의 혁신, NotebookLM 기반 교사 백과사전입니다.',
                'description': 'Eduitit의 모든 기능과 교육적 활용 팁을 한눈에 확인하세요. Google NotebookLM 기술을 활용하여 방대한 매뉴얼도 질문 하나로 즉시 해결할 수 있습니다.',
                'price': 0.00,
                'is_active': True,
                'icon': 'fa-solid fa-book-open',
                'color_theme': 'blue',
                'card_size': 'small',
                'service_type': 'guide',
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'Created product: {product.title}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Product already exists: {product.title}'))

        # 2. Product Features creation (SIS 1.15 - Minimum 3 features)
        features_data = [
            {
                'icon': 'fa-solid fa-magnifying-glass',
                'title': '지능형 검색',
                'description': '매뉴얼의 방대한 내용 중 필요한 정보만 AI가 즉시 찾아줍니다.'
            },
            {
                'icon': 'fa-solid fa-graduation-cap',
                'title': '교육적 활용 가이드',
                'description': '각 서비스별 학급 경영 및 수업 활용 팁을 제공합니다.'
            },
            {
                'icon': 'fa-solid fa-bolt',
                'title': '실시간 업데이트',
                'description': '관리자가 업데이트하는 최신 기능 설명을 가장 빠르게 확인하세요.'
            }
        ]

        for feature in features_data:
            feat, f_created = ProductFeature.objects.get_or_create(
                product=product,
                title=feature['title'],
                defaults={
                    'icon': feature['icon'],
                    'description': feature['description']
                }
            )
            if f_created:
                self.stdout.write(self.style.SUCCESS(f'  Added feature: {feat.title}'))

        self.stdout.write(self.style.SUCCESS('NotebookLM product setup complete.'))
