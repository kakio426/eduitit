
from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = 'Ensure Chess product exists in database'

    def handle(self, *args, **options):
        title = '두뇌 풀가동! 교실 체스'
        defaults = {
            'title': title,
            'lead_text': '준비물 없이 한 화면 대전과 AI 연습을 바로 시작하는 교실 체스입니다.',
            'description': '두뇌 풀가동! 교실 체스는 같은 화면에서 친구와 번갈아 두는 로컬 대전과 Stockfish 기반 AI 대전을 모두 지원하는 체스 서비스입니다. 규칙 보기와 플레이 진입 경로를 분리해 수업 중에도 안정적으로 시작할 수 있습니다.',
            'price': 0.00,
            'is_active': True,
            'is_featured': False,
            'is_guest_allowed': False,
            'icon': '♟️',
            'color_theme': 'dark',
            'card_size': 'small',
            'display_order': 14,
            'service_type': 'game',
            'external_url': '',
            'launch_route_name': 'chess:index',
        }
        mutable_fields = [
            'title',
            'lead_text',
            'description',
            'price',
            'is_active',
            'is_featured',
            'is_guest_allowed',
            'icon',
            'color_theme',
            'card_size',
            'display_order',
            'service_type',
            'external_url',
            'launch_route_name',
        ]

        chess = Product.objects.filter(title=title).first() or Product.objects.filter(title__icontains='체스').first()
        if chess is None:
            chess = Product.objects.create(**defaults)
            self.stdout.write(self.style.SUCCESS(f'Created product: {chess.title}'))
        else:
            changed = []
            for field in mutable_fields:
                new_value = defaults[field]
                if getattr(chess, field) != new_value:
                    setattr(chess, field, new_value)
                    changed.append(field)
            if changed:
                chess.save(update_fields=changed)
                self.stdout.write(self.style.SUCCESS(f'Updated product fields: {", ".join(changed)}'))

        feature_specs = [
            {
                'icon': '🤖',
                'title': '무료 AI 대전 (Stockfish)',
                'description': '세계 최강급 AI 엔진 Stockfish.js를 탑재했습니다. 4단계 난이도로 실력에 맞춰 연습할 수 있습니다.',
            },
            {
                'icon': '🤝',
                'title': '1대1 로컬 대전',
                'description': '친구와 한 화면에서 번갈아 두는 로컬 대전을 지원합니다.',
            },
            {
                'icon': '📜',
                'title': '규칙 가이드',
                'description': '체스 말 이동, 특수 규칙, 시작 흐름을 빠르게 확인할 수 있습니다.',
            },
        ]

        used_feature_ids = set()
        for item in feature_specs:
            feature = (
                ProductFeature.objects.filter(product=chess, title=item['title'])
                .exclude(id__in=used_feature_ids)
                .order_by('id')
                .first()
            )
            if feature is None:
                feature = (
                    ProductFeature.objects.filter(product=chess)
                    .exclude(id__in=used_feature_ids)
                    .order_by('id')
                    .first()
                )
            if feature is None:
                feature = ProductFeature.objects.create(product=chess, **item)
            else:
                changed = []
                if feature.icon != item['icon']:
                    feature.icon = item['icon']
                    changed.append('icon')
                if feature.title != item['title']:
                    feature.title = item['title']
                    changed.append('title')
                if feature.description != item['description']:
                    feature.description = item['description']
                    changed.append('description')
                if changed:
                    feature.save(update_fields=changed)
            used_feature_ids.add(feature.id)

        stale_features = ProductFeature.objects.filter(product=chess).exclude(id__in=used_feature_ids)
        if stale_features.exists():
            stale_features.delete()

        manual, _ = ServiceManual.objects.get_or_create(
            product=chess,
            defaults={
                'title': '교실 체스 사용법',
                'description': '로컬 대전, AI 대전, 규칙 보기 흐름을 바로 따라갈 수 있습니다.',
                'is_published': True,
            },
        )
        manual_changed = []
        if manual.title != '교실 체스 사용법':
            manual.title = '교실 체스 사용법'
            manual_changed.append('title')
        if manual.description != '로컬 대전, AI 대전, 규칙 보기 흐름을 바로 따라갈 수 있습니다.':
            manual.description = '로컬 대전, AI 대전, 규칙 보기 흐름을 바로 따라갈 수 있습니다.'
            manual_changed.append('description')
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append('is_published')
        if manual_changed:
            manual.save(update_fields=manual_changed)

        section_specs = [
            ('시작하기', '교실 체스를 열고 로컬 대전 또는 AI 대전을 선택해 시작합니다.', 1),
            ('AI 대전', 'easy, medium, hard, expert 4단계 난이도 중 하나를 골라 AI와 대전합니다.', 2),
            ('규칙 가이드', '규칙 보기 화면에서 말 이동과 특수 규칙을 먼저 익힌 뒤 플레이하면 안정적으로 시작할 수 있습니다.', 3),
        ]
        used_section_ids = set()
        for title_text, content, order in section_specs:
            section = (
                ManualSection.objects.filter(manual=manual, title=title_text)
                .exclude(id__in=used_section_ids)
                .order_by('display_order', 'id')
                .first()
            )
            if section is None:
                section = (
                    ManualSection.objects.filter(manual=manual, display_order=order)
                    .exclude(id__in=used_section_ids)
                    .order_by('id')
                    .first()
                )
            if section is None:
                section = ManualSection.objects.create(
                    manual=manual,
                    title=title_text,
                    content=content,
                    display_order=order,
                )
            else:
                changed = []
                if section.title != title_text:
                    section.title = title_text
                    changed.append('title')
                if section.content != content:
                    section.content = content
                    changed.append('content')
                if section.display_order != order:
                    section.display_order = order
                    changed.append('display_order')
                if changed:
                    section.save(update_fields=changed)
            used_section_ids.add(section.id)

        stale_sections = ManualSection.objects.filter(manual=manual).exclude(id__in=used_section_ids)
        if stale_sections.exists():
            stale_sections.delete()
