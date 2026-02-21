from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Ensure Insight Library product exists in database'

    def handle(self, *args, **options):
        from products.models import Product, ProductFeature, ServiceManual, ManualSection

        product, created = Product.objects.get_or_create(
            title='Insight Library',
            defaults={
                'lead_text': '선생님의 시선으로 AI 시대를 기록하다',
                'description': (
                    '유튜브 영상, 개발 일지, 칼럼 등 선생님이 발견한 인사이트를 카드 형태로 기록하고 공유하는 공간입니다. '
                    '영상 링크 하나로 썸네일이 자동 생성되고, 나만의 노트와 태그를 붙여 지식을 체계적으로 관리할 수 있습니다.'
                ),
                'price': 0.00,
                'is_active': True,
                'icon': '✨',
                'color_theme': 'indigo',
                'card_size': 'small',
                'service_type': 'tool',
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS('[ensure_insights] Product created'))
        else:
            self.stdout.write('[ensure_insights] Product already exists')

        # ProductFeature 최소 3개 (SIS Rule)
        features_data = [
            {
                'title': '유튜브 자동 썸네일',
                'description': 'YouTube URL을 입력하면 썸네일이 자동 생성됩니다.',
                'icon': '▶️',
            },
            {
                'title': '카테고리 & 태그 필터',
                'description': 'YouTube / DevLog / Column으로 분류하고, 태그 클릭으로 관련 인사이트를 즉시 탐색합니다.',
                'icon': '🏷️',
            },
            {
                'title': 'Featured 고정 & 좋아요',
                'description': '중요한 인사이트를 상단에 고정하고, 좋아요로 인기 콘텐츠를 구분합니다.',
                'icon': '⭐',
            },
        ]
        for data in features_data:
            ProductFeature.objects.get_or_create(
                product=product,
                title=data['title'],
                defaults={
                    'description': data['description'],
                    'icon': data['icon'],
                }
            )

        # ServiceManual + ManualSection (MUST)
        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                'title': 'Insight Library 사용법',
                'is_published': True,
            }
        )
        if manual.sections.count() == 0:
            ManualSection.objects.create(
                manual=manual,
                title='시작하기',
                content=(
                    '로그인 후 상단의 기록하기 버튼 또는 목록 하단의 + 카드를 클릭합니다. '
                    'YouTube URL을 입력하면 썸네일이 자동으로 생성됩니다. '
                    '핵심 인사이트 문구와 나만의 노트를 추가하고 저장하세요.'
                ),
                display_order=1,
            )
            ManualSection.objects.create(
                manual=manual,
                title='카테고리 & 태그 활용',
                content=(
                    'YouTube Scrap, DevLog, Column 세 가지 카테고리로 인사이트를 분류할 수 있습니다. '
                    '태그는 #AI교육 #미래교육처럼 공백으로 구분하여 여러 개 입력 가능합니다. '
                    '목록 페이지에서 태그를 클릭하면 같은 태그의 인사이트만 필터링됩니다.'
                ),
                display_order=2,
            )
            ManualSection.objects.create(
                manual=manual,
                title='Featured & 인기순 정렬',
                content=(
                    '관리자(Admin)에서 is_featured를 체크하면 해당 인사이트가 목록 상단에 고정됩니다. '
                    '인기순 정렬을 사용하면 좋아요가 많은 인사이트가 먼저 표시됩니다. '
                    '수정/삭제 버튼은 관리자 계정에서만 카드에 표시됩니다.'
                ),
                display_order=3,
            )
            self.stdout.write(self.style.SUCCESS('[ensure_insights] ServiceManual + 3 sections created'))

        self.stdout.write(self.style.SUCCESS('[ensure_insights] Done'))
