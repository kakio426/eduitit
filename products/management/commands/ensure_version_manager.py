from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = 'Ensure 최종최최종은 이제그만 product exists in database'

    def handle(self, *args, **options):
        title = '최종최최종은 이제그만'
        defaults = {
            'lead_text': '업로드 한 번으로 최신본과 배포본을 분리 관리하세요.',
            'description': '최종최최종은 이제그만은 교실 문서를 버전 단위로 자동 정리해 최신본과 공식 배포본을 분리 관리합니다. 선생님은 파일명을 신경 쓰지 않고 드롭만 하면 되고, 필요한 시점에 배포본 지정 버튼 한 번으로 공식본을 확정할 수 있습니다.',
            'price': 0.00,
            'is_active': True,
            'is_featured': False,
            'is_guest_allowed': False,
            'icon': '🗂️',
            'color_theme': 'blue',
            'card_size': 'small',
            'display_order': 26,
            'service_type': 'work',
            'external_url': '',
        }
        mutable_fields = ['lead_text', 'description', 'price', 'is_guest_allowed', 'icon', 'external_url']

        product, created = Product.objects.get_or_create(
            title=title,
            defaults=defaults,
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'Created product: {product.title}'))
        else:
            changed = []
            for field in mutable_fields:
                new_value = defaults[field]
                if getattr(product, field) != new_value:
                    setattr(product, field, new_value)
                    changed.append(field)
            if changed:
                product.save(update_fields=changed)
                self.stdout.write(self.style.SUCCESS(f'Updated product fields: {", ".join(changed)}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Product already exists: {product.title}'))

        features = [
            {
                'icon': '🔢',
                'title': '버전 자동 증가',
                'description': '같은 문서 패키지 안에서 업로드할 때마다 v01, v02처럼 자동으로 버전이 올라갑니다.',
            },
            {
                'icon': '📦',
                'title': '파일명·폴더 자동 정리',
                'description': '날짜, 문서명, 버전이 포함된 규칙 파일명과 월별 폴더 구조를 자동으로 생성합니다.',
            },
            {
                'icon': '✅',
                'title': '최신본·배포본 분리',
                'description': '최신본은 자동으로 갱신하고, 공식 배포본은 필요할 때만 수동 지정해 실수 배포를 막습니다.',
            },
        ]

        for item in features:
            _, feature_created = ProductFeature.objects.get_or_create(
                product=product,
                title=item['title'],
                defaults={'icon': item['icon'], 'description': item['description']},
            )
            if feature_created:
                self.stdout.write(self.style.SUCCESS(f'  Added feature: {item["title"]}'))

        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                'title': '최종최최종은 이제그만 사용법',
                'description': '문서 생성부터 최신본/배포본 다운로드까지의 핵심 흐름을 안내합니다.',
                'is_published': True,
            },
        )

        manual_changed = []
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append('is_published')
        if not manual.description:
            manual.description = '문서 생성부터 최신본/배포본 다운로드까지의 핵심 흐름을 안내합니다.'
            manual_changed.append('description')
        if manual_changed:
            manual.save(update_fields=manual_changed)

        sections = [
            (
                '시작하기(문서 생성·업로드)',
                '새 문서에서 문서명과 그룹을 정한 뒤 파일을 업로드하면 버전이 자동으로 쌓입니다.',
                1,
            ),
            (
                '파일명/버전 규칙',
                '업로드 파일은 YYYY-MM-DD_문서명_vNN 형식으로 자동 저장되며 같은 문서 안에서 버전이 증가합니다.',
                2,
            ),
            (
                '최신본/배포본 사용법',
                '최신본은 항상 가장 최근 업로드를 가리키며 배포본은 권한자가 버튼으로 확정할 때만 변경됩니다.',
                3,
            ),
        ]

        for section_title, content, order in sections:
            section, section_created = ManualSection.objects.get_or_create(
                manual=manual,
                title=section_title,
                defaults={'content': content, 'display_order': order},
            )
            if not section_created:
                changed = []
                if section.display_order != order:
                    section.display_order = order
                    changed.append('display_order')
                if not section.content:
                    section.content = content
                    changed.append('content')
                if changed:
                    section.save(update_fields=changed)

        self.stdout.write(self.style.SUCCESS('최종최최종은 이제그만 ensure 작업 완료'))
