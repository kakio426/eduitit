from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure 행복의 씨앗 product exists in database"

    def handle(self, *args, **options):
        title = "행복의 씨앗"
        defaults = {
            "lead_text": "작은 행동이 모이면, 행복이 자랍니다.",
            "description": (
                "행복의 씨앗은 초등 교실에서 긍정 행동을 씨앗과 꽃피움으로 연결해 "
                "참여 의지와 습관 형성을 돕는 운영 플랫폼입니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": True,
            "icon": "🌱",
            "color_theme": "green",
            "card_size": "small",
            "display_order": 27,
            "service_type": "classroom",
            "external_url": "",
        }
        mutable_fields = [
            "lead_text",
            "description",
            "price",
            "is_active",
            "is_guest_allowed",
            "icon",
            "external_url",
        ]

        product, created = Product.objects.get_or_create(
            title=title,
            defaults=defaults,
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created product: {product.title}"))
        else:
            changed = []
            for field in mutable_fields:
                new_value = defaults[field]
                if getattr(product, field) != new_value:
                    setattr(product, field, new_value)
                    changed.append(field)
            if changed:
                product.save(update_fields=changed)
                self.stdout.write(self.style.SUCCESS(f"Updated product fields: {', '.join(changed)}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"Product already exists: {product.title}"))

        features = [
            {
                "icon": "🌸",
                "title": "꽃피움 랜덤 보상",
                "description": "긍정 행동을 기반으로 꽃피움 기회를 제공하는 랜덤 보상 시스템입니다.",
            },
            {
                "icon": "🏡",
                "title": "학급 꽃밭",
                "description": "빈 정원에서 시작해 1년 동안 함께 자라는 공개 꽃밭 대시보드를 제공합니다.",
            },
            {
                "icon": "📊",
                "title": "교사 분석",
                "description": "학생별 참여, 당첨, 씨앗 누적 흐름을 확인하는 교사용 분석 보드를 지원합니다.",
            },
        ]
        for item in features:
            _, feature_created = ProductFeature.objects.get_or_create(
                product=product,
                title=item["title"],
                defaults={"icon": item["icon"], "description": item["description"]},
            )
            if feature_created:
                self.stdout.write(self.style.SUCCESS(f"  Added feature: {item['title']}"))

        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": "행복의 씨앗 시작 가이드",
                "description": "교실 생성부터 씨앗/꽃피움 운영까지 핵심 흐름을 빠르게 안내합니다.",
                "is_published": True,
            },
        )

        manual_changed = []
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        if not manual.description:
            manual.description = "교실 생성부터 씨앗/꽃피움 운영까지 핵심 흐름을 빠르게 안내합니다."
            manual_changed.append("description")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        sections = [
            (
                "시작하기",
                (
                    "1) 교실 생성 -> 2) 학생 등록 -> 3) 동의 관리에서 서명톡 링크 생성 순서로 시작합니다. "
                    "보호자 동의가 완료된 학생만 기록 저장 및 보상 지급이 가능합니다."
                ),
                1,
            ),
            (
                "주요 기능",
                (
                    "성실 참여/우수 성취 티켓 부여, 미당첨 씨앗 +1, 씨앗 N개 자동 티켓 전환, "
                    "꽃피움 추첨(교사 수동 종료 축하 화면)을 운영합니다."
                ),
                2,
            ),
            (
                "보상 확률 설정",
                (
                    "보상마다 선택 확률(%)을 설정할 수 있습니다. "
                    "해당 값은 '당첨 발생 시 어떤 보상을 줄지'를 정하는 상대 가중치로 동작합니다."
                ),
                3,
            ),
            (
                "동의 운영",
                (
                    "동의 관리 화면에서 서명톡 링크를 생성하면 학생 동의 항목에 자동 반영됩니다. "
                    "링크 공유 후 제출 현황을 확인해 동의완료 상태로 전환하세요."
                ),
                4,
            ),
            (
                "사용 팁",
                "비교 대신 행동 언어를 사용하고, 축하 장면은 교사가 직접 마무리해 주세요.",
                5,
            ),
        ]
        for section_title, content, order in sections:
            section, section_created = ManualSection.objects.get_or_create(
                manual=manual,
                title=section_title,
                defaults={"content": content, "display_order": order},
            )
            if not section_created:
                changed = []
                if section.display_order != order:
                    section.display_order = order
                    changed.append("display_order")
                if not section.content:
                    section.content = content
                    changed.append("content")
                if changed:
                    section.save(update_fields=changed)

        self.stdout.write(self.style.SUCCESS("ensure_happy_seed completed"))
