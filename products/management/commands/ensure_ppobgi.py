from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure 별빛 추첨기 product exists in database"

    def handle(self, *args, **options):
        title = "별빛 추첨기"
        defaults = {
            "lead_text": "교사용 TV에서 별빛, 사다리, 순서, 팀, 유성우, 역할 카드를 반짝이는 교실 쇼처럼 바로 띄울 수 있습니다.",
            "description": (
                "별빛 추첨기는 교사가 큰 화면에서 학급 명단을 불러와 별빛 추첨, 사다리 뽑기, 순서 뽑기, 팀 나누기, 유성우 뽑기, 역할 카드 발표를 "
                "하나의 교실 쇼처럼 운영하는 서비스입니다. 사용자별 명단 복원, 학급 우선 불러오기, 발표 오버레이, 효과음, 비복원 추첨, 발표 기록을 기본 제공합니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "✨",
            "color_theme": "dark",
            "card_size": "small",
            "display_order": 31,
            "service_type": "classroom",
            "external_url": "",
            "launch_route_name": "ppobgi:main",
        }
        mutable_fields = [
            "lead_text",
            "description",
            "price",
            "is_guest_allowed",
            "icon",
            "external_url",
            "launch_route_name",
        ]

        product, created = Product.objects.get_or_create(title=title, defaults=defaults)
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

        feature_specs = [
            {
                "icon": "🧾",
                "title": "학급 명단 바로 시작",
                "description": "붙여넣기나 당번 명단 불러오기로 준비하고, 사용자·학급 기준으로 안전하게 이어서 시작합니다.",
            },
            {
                "icon": "✨",
                "title": "6가지 발표 모드",
                "description": "별빛, 사다리, 순서, 팀, 유성우, 역할 카드를 수업 흐름에 맞게 바로 전환할 수 있습니다.",
            },
            {
                "icon": "🏆",
                "title": "대형 화면 쇼 발표",
                "description": "결과를 큰 타이포와 공통 발표 오버레이, 효과음으로 또렷하게 보여 주고 다음 진행으로 바로 이어집니다.",
            },
        ]

        for item in feature_specs:
            feature, feature_created = ProductFeature.objects.get_or_create(
                product=product,
                title=item["title"],
                defaults={"icon": item["icon"], "description": item["description"]},
            )
            if not feature_created:
                changed = []
                if feature.icon != item["icon"]:
                    feature.icon = item["icon"]
                    changed.append("icon")
                if feature.description != item["description"]:
                    feature.description = item["description"]
                    changed.append("description")
                if changed:
                    feature.save(update_fields=changed)

        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": "별빛 추첨기 사용 가이드",
                "description": "대화면에서 6가지 교실 쇼 모드를 바로 열고 발표하는 흐름을 빠르게 따라갈 수 있습니다.",
                "is_published": True,
            },
        )

        manual_changed = []
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        target_desc = "대화면에서 6가지 교실 쇼 모드를 바로 열고 발표하는 흐름을 빠르게 따라갈 수 있습니다."
        if manual.description != target_desc:
            manual.description = target_desc
            manual_changed.append("description")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        sections = [
            (
                "시작하기",
                "교사용 TV나 데스크톱에서 명단을 붙여넣거나 학급 명단을 불러온 뒤 원하는 모드를 눌러 바로 쇼를 시작합니다.",
                1,
            ),
            (
                "발표 진행",
                "별빛, 사다리, 순서, 팀, 유성우, 역할 카드 중 현재 수업 흐름에 맞는 모드를 선택하고 한 명씩 크게 공개합니다.",
                2,
            ),
            (
                "수업 활용 팁",
                "효과음은 기본 켜짐이지만 바로 끌 수 있으므로 집중 활동, 발표 순서, 팀 구성, 역할 소개를 상황에 맞게 자연스럽게 이어갈 수 있습니다.",
                3,
            ),
        ]
        for section_title, content, order in sections:
            section, created_section = ManualSection.objects.get_or_create(
                manual=manual,
                title=section_title,
                defaults={"content": content, "display_order": order},
            )
            if not created_section:
                changed = []
                if section.content != content:
                    section.content = content
                    changed.append("content")
                if section.display_order != order:
                    section.display_order = order
                    changed.append("display_order")
                if changed:
                    section.save(update_fields=changed)

        self.stdout.write(self.style.SUCCESS("ensure_ppobgi completed"))
