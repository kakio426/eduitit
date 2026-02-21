from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure 별빛 추첨기 product exists in database"

    def handle(self, *args, **options):
        title = "별빛 추첨기"
        defaults = {
            "lead_text": "교사용 TV에서 명단을 붙여넣고 별 하나를 고르면, 오늘의 주인공을 감성적으로 뽑아줍니다.",
            "description": (
                "별빛 추첨기는 교사가 큰 화면에서 학급 명단을 입력하고 별을 클릭해 1명을 랜덤 추첨하는 서비스입니다. "
                "중복 이름 정리, 최대 인원 제한, 비복원 추첨, 추첨 히스토리를 기본 제공해 수업 진행 흐름이 명확합니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "✨",
            "color_theme": "dark",
            "card_size": "small",
            "display_order": 31,
            "service_type": "game",
            "external_url": "",
            "launch_route_name": "ppobgi:main",
        }
        mutable_fields = [
            "lead_text",
            "description",
            "price",
            "is_active",
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
                "title": "명단 붙여넣기",
                "description": "줄바꿈 기준으로 이름을 빠르게 입력하고 즉시 추첨 우주를 생성합니다.",
            },
            {
                "icon": "🌌",
                "title": "별 선택 추첨",
                "description": "빛나는 별 중 하나를 직접 눌러 오늘의 주인공을 뽑을 수 있습니다.",
            },
            {
                "icon": "🏆",
                "title": "결과 발표 화면",
                "description": "선택된 이름을 대형 타이포로 보여주고 다음 추첨까지 바로 이어갈 수 있습니다.",
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
                "description": "명단 입력부터 추첨, 결과 발표까지 기본 사용 흐름을 안내합니다.",
                "is_published": True,
            },
        )

        manual_changed = []
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        target_desc = "명단 입력부터 추첨, 결과 발표까지 기본 사용 흐름을 안내합니다."
        if manual.description != target_desc:
            manual.description = target_desc
            manual_changed.append("description")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        sections = [
            (
                "시작하기",
                "입력창에 이름을 한 줄씩 넣고 '우주에 흩뿌리기' 버튼을 누르면 추첨 화면이 열립니다.",
                1,
            ),
            (
                "추첨 진행",
                "학생이 별 하나를 직접 눌러 선택하게 하면 랜덤성이 눈에 보이는 방식으로 전달됩니다.",
                2,
            ),
            (
                "수업 활용 팁",
                "발표자, 칠판 정리 담당, 활동 순서를 정할 때 빠르게 1명을 공정하게 뽑을 수 있습니다.",
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
