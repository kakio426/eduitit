from django.core.management.base import BaseCommand
from products.models import Product, ProductFeature, ServiceManual, ManualSection


class Command(BaseCommand):
    help = 'Ensure ClassCalendar product and manual exist in database'

    def handle(self, *args, **options):
        # 1. Product 보장
        product, created = Product.objects.get_or_create(
            launch_route_name='classcalendar:main',
            defaults={
                'title': '학급 캘린더',
                'lead_text': '에듀잇과 구글 일정을 한곳에서!',
                'description': '에듀잇의 예약/수합 일정과 구글 캘린더를 함께 확인하고 관리하는 강력한 학급 전용 캘린더입니다.',
                'price': 0.00,
                'is_active': True,
                'icon': '📅',
                'color_theme': 'blue',
                'card_size': 'small',
                'service_type': 'classroom',
                'display_order': 99,
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'Created product: {product.title}'))
        else:
            # 필수 식별자만 보정하고, 나머지 마케팅 문구는 관리자 수정을 보존한다.
            update_fields = []
            if product.title != '학급 캘린더':
                product.title = '학급 캘린더'
                update_fields.append('title')
            if product.icon != '📅':
                product.icon = '📅'
                update_fields.append('icon')
            if product.launch_route_name != 'classcalendar:main':
                product.launch_route_name = 'classcalendar:main'
                update_fields.append('launch_route_name')
            if not product.is_active:
                product.is_active = True
                update_fields.append('is_active')
            if update_fields:
                product.save(update_fields=update_fields)
                self.stdout.write(self.style.SUCCESS(f'Updated product essentials: {product.title}'))

        # 2. Product Features
        features = [
            {'title': '에듀잇 일정 통합', 'description': '예약, 수합, 상담 등 에듀잇의 모든 일정을 한눈에 모아봅니다.', 'icon': '🔗'},
            {'title': '구글 캘린더 연동', 'description': '기존에 쓰시던 구글 캘린더 일정을 그대로 불러와 통합 관리할 수 있습니다.', 'icon': '☁️'},
            {'title': '노션형 이벤트 페이지', 'description': '단순한 일정을 넘어 텍스트, 체크리스트, 파일 등이 포함된 풍부한 이벤트 페이지를 만듭니다.', 'icon': '📝'},
        ]

        for feat in features:
            pf, _ = ProductFeature.objects.get_or_create(
                product=product,
                title=feat['title'],
                defaults={'description': feat['description'], 'icon': feat['icon']}
            )
            feature_updates = []
            if pf.description != feat['description']:
                pf.description = feat['description']
                feature_updates.append('description')
            if pf.icon != feat['icon']:
                pf.icon = feat['icon']
                feature_updates.append('icon')
            if feature_updates:
                pf.save(update_fields=feature_updates)

        # 3. Service Manual 보장 (SIS MUST 규칙)
        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                'title': f'{product.title} 사용법',
                'description': '학급 일정 관리와 구글 캘린더 연동 방법을 단계별로 안내합니다.',
                'is_published': True
            }
        )
        manual_update_fields = []
        expected_manual_title = f'{product.title} 사용법'
        if manual.title != expected_manual_title:
            manual.title = expected_manual_title
            manual_update_fields.append('title')
        if not manual.is_published:
            manual.is_published = True
            manual_update_fields.append('is_published')
        expected_manual_description = '학급 일정 관리와 구글 캘린더 연동 방법을 단계별로 안내합니다.'
        if manual.description != expected_manual_description:
            manual.description = expected_manual_description
            manual_update_fields.append('description')
        if manual_update_fields:
            manual.save(update_fields=manual_update_fields)

        section_specs = [
            (
                '시작하기',
                '학급 캘린더에 오신 것을 환영합니다! 먼저 구글 캘린더 연동을 완료하면 기존 일정을 빠르게 불러올 수 있습니다.',
                1,
            ),
            (
                '주요 기능',
                '- 구글 일정 가져오기\n- 노션형 이벤트 블록 메모\n- 학생용 아젠다 공유',
                2,
            ),
            (
                '활용 팁',
                'Today 지휘소와 함께 사용하면 오늘 일정과 학급 운영 업무를 한 화면에서 관리할 수 있습니다.',
                3,
            ),
        ]
        for section_title, section_content, section_order in section_specs:
            section, _ = ManualSection.objects.get_or_create(
                manual=manual,
                title=section_title,
                defaults={
                    'content': section_content,
                    'display_order': section_order,
                },
            )
            section_update_fields = []
            if section.content != section_content:
                section.content = section_content
                section_update_fields.append('content')
            if section.display_order != section_order:
                section.display_order = section_order
                section_update_fields.append('display_order')
            if section_update_fields:
                section.save(update_fields=section_update_fields)

        self.stdout.write(self.style.SUCCESS('Successfully ensured classcalendar product and manual.'))
