"""
Railway에서 실행할 제품 데이터 수정 명령

실행 방법:
python manage.py fix_products
"""
from django.core.management.base import BaseCommand
from products.models import Product


class Command(BaseCommand):
    help = '제품 데이터 수정: 윷놀이 featured 해제 & 쌤BTI 생성'

    def handle(self, *args, **options):
        self.stdout.write("=" * 60)
        self.stdout.write("제품 데이터 수정 시작")
        self.stdout.write("=" * 60)

        # 1. 모든 제품의 card_size를 small로 변경
        updated = Product.objects.all().update(card_size='small')
        self.stdout.write(f"✓ {updated}개 제품의 card_size를 small로 변경")

        # 2. 윷놀이 is_featured를 False로 변경
        yut_updated = Product.objects.filter(
            title__icontains='윷'
        ).update(is_featured=False)
        self.stdout.write(f"✓ 윷놀이 is_featured를 False로 변경 ({yut_updated}개)")

        # 3. 쌤BTI 생성 (없는 경우에만)
        ssambti_exists = Product.objects.filter(title__icontains="쌤BTI").exists()

        if not ssambti_exists:
            ssambti = Product.objects.create(
                title="쌤BTI",
                description="12가지 간단한 질문으로 알아보는 나의 교실 속 영혼의 동물! 동료 선생님들과 쌤BTI를 공유하고 서로의 스타일을 알아보세요.",
                lead_text="나는 교실에서 어떤 동물일까? 1분 만에 알아보는 교사 본캐 테스트!",
                icon="🦁",
                price=0,
                is_active=True,
                is_featured=False,
                color_theme="orange",
                card_size="small",
                display_order=0,
                service_type="tool",
                external_url="/ssambti/",
            )
            self.stdout.write(f"✓ 쌤BTI 생성됨 (ID: {ssambti.id})")
        else:
            self.stdout.write("✓ 쌤BTI 이미 존재함")

        # 4. 최종 확인
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("최종 상태 확인")
        self.stdout.write("=" * 60)

        yut = Product.objects.filter(title__icontains='윷').first()
        ssambti = Product.objects.filter(title__icontains='BTI').first()

        if yut:
            self.stdout.write(f"윷놀이 is_featured: {yut.is_featured}")
            self.stdout.write(f"윷놀이 card_size: {yut.card_size}")

        if ssambti:
            self.stdout.write(f"쌤BTI 존재: True (ID: {ssambti.id})")
            self.stdout.write(f"쌤BTI display_order: {ssambti.display_order}")
            self.stdout.write(f"쌤BTI card_size: {ssambti.card_size}")
        else:
            self.stdout.write("쌤BTI 존재: False")

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("완료!"))
        self.stdout.write("=" * 60)
