from django.core.management.base import BaseCommand
from products.models import Product, ProductFeature, ServiceManual, ManualSection

TARGET_ROUTE = "classcalendar:main"
LEGACY_TITLES = ("교무수첩", "학급 캘린더")


class Command(BaseCommand):
    help = 'Ensure ClassCalendar product and manual exist in database'

    def handle(self, *args, **options):
        # 1. Product 보장
        product = Product.objects.filter(launch_route_name=TARGET_ROUTE).order_by("id").first()
        created = False
        if not product:
            product = Product.objects.filter(title__in=LEGACY_TITLES).order_by("-is_active", "id").first()
        if not product:
            product = Product.objects.create(
                title='교무수첩',
                lead_text='학급 일정을 한눈에 관리하세요!',
                description='학급 운영 일정을 한곳에서 정리하고 공유하는 학급 전용 캘린더입니다.',
                price=0.00,
                is_active=True,
                icon='📅',
                color_theme='blue',
                card_size='small',
                service_type='classroom',
                display_order=99,
                launch_route_name=TARGET_ROUTE,
                external_url="",
            )
            created = True

        if created:
            self.stdout.write(self.style.SUCCESS(f'Created product: {product.title}'))
        else:
            # 필수 라우팅/가시성만 보정하고, 마케팅 문구 및 순서는 관리자 수정을 보존한다.
            update_fields = []
            if product.launch_route_name != TARGET_ROUTE:
                product.launch_route_name = TARGET_ROUTE
                update_fields.append("launch_route_name")
            if product.external_url:
                product.external_url = ""
                update_fields.append("external_url")
            if (product.service_type or "").strip() != "classroom":
                product.service_type = "classroom"
                update_fields.append("service_type")
            if not (product.icon or "").strip():
                product.icon = "📅"
                update_fields.append("icon")
            if update_fields:
                product.save(update_fields=update_fields)
                self.stdout.write(self.style.SUCCESS(f'Updated product essentials: {product.title}'))

        # 1-1. 레거시 타이틀 제품도 라우트를 SSOT로 보정 (교무수첩 상세 fallback 방지)
        legacy_count = 0
        for legacy in Product.objects.filter(title__in=LEGACY_TITLES):
            legacy_updates = []
            if legacy.launch_route_name != TARGET_ROUTE:
                legacy.launch_route_name = TARGET_ROUTE
                legacy_updates.append("launch_route_name")
            if legacy.external_url:
                legacy.external_url = ""
                legacy_updates.append("external_url")
            if legacy_updates:
                legacy.save(update_fields=legacy_updates)
                legacy_count += 1
        if legacy_count:
            self.stdout.write(self.style.SUCCESS(f'Normalized legacy classcalendar products: {legacy_count}'))

        # 2. Product Features
        features = [
            {'title': '에듀잇 일정 통합', 'description': '예약, 수합, 상담 등 에듀잇의 모든 일정을 한눈에 모아봅니다.', 'icon': '🔗'},
            {'title': '블록형 일정 노트', 'description': '일정마다 텍스트, 체크리스트, 링크/파일 메모를 블록으로 정리할 수 있습니다.', 'icon': '📝'},
            {'title': '교사 전용 운영', 'description': '일정은 교사 계정 내부에서만 관리되며 외부 공개 링크가 없습니다.', 'icon': '🔒'},
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
                'description': '학급 일정 관리 방법을 단계별로 안내합니다.',
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
        expected_manual_description = '학급 일정 관리 방법을 단계별로 안내합니다.'
        if manual.description != expected_manual_description:
            manual.description = expected_manual_description
            manual_update_fields.append('description')
        if manual_update_fields:
            manual.save(update_fields=manual_update_fields)

        section_specs = [
            (
                '시작하기',
                '학급 캘린더에 오신 것을 환영합니다! 먼저 학급 일정을 등록해 보세요.',
                1,
            ),
            (
                '주요 기능',
                '- 에듀잇 일정 통합\n- 블록형 일정 노트\n- 교사 전용 운영',
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
