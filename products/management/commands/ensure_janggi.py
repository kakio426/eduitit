from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = 'Ensure Janggi product exists in database'

    def handle(self, *args, **options):
        title = '두뇌 풀가동! 교실 장기'
        defaults = {
            'lead_text': '설치 없이 바로, 교실에서 장기 로컬 대전과 AI 대전을 시작하세요.',
            'description': '두뇌 풀가동! 교실 장기는 체스 서비스 구조를 그대로 따라 로컬 대전과 AI 대전을 빠르게 시작할 수 있는 장기 서비스입니다. 수업 중 짧은 활동 시간에도 바로 접속해 게임을 진행하고, AI 난이도를 단계적으로 올리며 연습할 수 있습니다.',
            'price': 0.00,
            'is_active': True,
            'is_featured': False,
            'is_guest_allowed': False,
            'icon': '🧠',
            'color_theme': 'dark',
            'card_size': 'small',
            'display_order': 15,
            'service_type': 'game',
            'external_url': '',
        }

        mutable_fields = ['lead_text', 'description', 'price', 'is_active', 'is_guest_allowed', 'icon', 'external_url']

        product, created = Product.objects.get_or_create(
            title=title,
            defaults=defaults,
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'Created product: {title}'))
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
                self.stdout.write(self.style.SUCCESS(f'Product already exists: {title}'))

        features = [
            {
                'icon': '👥',
                'title': '한 화면 로컬 대전',
                'description': '학생 둘이 같은 화면에서 번갈아 수를 두며 장기 기본기를 익힐 수 있습니다.',
            },
            {
                'icon': '🤖',
                'title': 'AI 대전 구조',
                'description': '체스와 동일한 Worker+UCI 구조로 장기 AI 엔진을 연결할 수 있도록 설계했습니다.',
            },
            {
                'icon': '📚',
                'title': '규칙 가이드',
                'description': '궁성, 차·마·상·포 핵심 이동 규칙을 수업용 문장으로 빠르게 확인할 수 있습니다.',
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
                'title': '교실 장기 사용법',
                'description': '로컬 대전 시작부터 AI 모드 연결까지 교실 적용 흐름을 안내합니다.',
                'is_published': True,
            },
        )

        manual_changed = []
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append('is_published')
        if not manual.description:
            manual.description = '로컬 대전 시작부터 AI 모드 연결까지 교실 적용 흐름을 안내합니다.'
            manual_changed.append('description')
        if manual_changed:
            manual.save(update_fields=manual_changed)

        sections = [
            ('시작하기', '대시보드에서 교실 장기를 열고 로컬 또는 AI 모드를 선택해 게임을 시작합니다.', 1),
            ('AI 모드 연결', 'Worker 기반 엔진을 시작하고 UCI 로그로 엔진 준비 상태와 bestmove 응답을 확인합니다.', 2),
            ('수업 활용 팁', '처음에는 로컬 대전으로 규칙을 익히고 이후 AI 난이도를 단계적으로 올리세요.', 3),
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

        self.stdout.write(self.style.SUCCESS('교실 장기 ensure 작업 완료'))

