from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure blockclass product and manual exist in database"

    def handle(self, *args, **options):
        title = "블록활동 실습실"
        defaults = {
            "lead_text": "블록을 끌어 놓고 JSON과 활동판 이미지를 바로 저장할 수 있는 Blockly 실습실입니다.",
            "description": (
                "수업 순서, 조건 활동, 반복 연습처럼 블록 기반 설명 자료를 빠르게 만들고 저장할 때 쓰는 교사용 실습 도구입니다. "
                "브라우저 안에서 템플릿을 바꾸고, JSON 저장과 이미지 저장으로 바로 이어갈 수 있습니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "🧩",
            "color_theme": "green",
            "card_size": "small",
            "display_order": 27,
            "service_type": "classroom",
            "external_url": "",
            "launch_route_name": "blockclass:main",
            "solve_text": "블록 활동판을 바로 만들고 싶어요",
            "result_text": "Blockly 활동판과 코드 보기",
            "time_text": "5분",
        }
        product, created = Product.objects.get_or_create(title=title, defaults=defaults)

        if created:
            self.stdout.write(self.style.SUCCESS("[ensure_blockclass] Product created"))
        else:
            changed_fields = []
            if not product.is_active:
                product.is_active = True
                changed_fields.append("is_active")
            if not (product.launch_route_name or "").strip():
                product.launch_route_name = defaults["launch_route_name"]
                changed_fields.append("launch_route_name")
            valid_service_types = {code for code, _ in Product.SERVICE_CHOICES}
            if product.service_type not in valid_service_types:
                product.service_type = defaults["service_type"]
                changed_fields.append("service_type")
            valid_color_themes = {code for code, _ in Product.COLOR_CHOICES}
            if product.color_theme not in valid_color_themes:
                product.color_theme = defaults["color_theme"]
                changed_fields.append("color_theme")
            if changed_fields:
                product.save(update_fields=changed_fields)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[ensure_blockclass] Product fields updated: {', '.join(changed_fields)}"
                    )
                )

        features = [
            {
                "icon": "🧱",
                "title": "템플릿 바로 시작",
                "description": "순서, 조건, 반복 예시 템플릿으로 빈 화면에서 바로 시작할 수 있습니다.",
            },
            {
                "icon": "💾",
                "title": "로컬 JSON 저장",
                "description": "현재 워크스페이스를 JSON 파일로 저장하고 다시 불러올 수 있습니다.",
            },
            {
                "icon": "🖼️",
                "title": "활동판 이미지 저장",
                "description": "워크스페이스를 SVG 활동판으로 저장해 수업 자료로 바로 쓸 수 있습니다.",
            },
        ]
        for feature in features:
            ProductFeature.objects.get_or_create(
                product=product,
                title=feature["title"],
                defaults=feature,
            )

        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": "블록활동 실습실 사용 가이드",
                "description": "템플릿 선택부터 JSON 저장, 활동판 이미지 저장까지 빠르게 익히는 안내입니다.",
                "is_published": True,
            },
        )

        manual_changed = []
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        if not (manual.description or "").strip():
            manual.description = "템플릿 선택부터 JSON 저장, 활동판 이미지 저장까지 빠르게 익히는 안내입니다."
            manual_changed.append("description")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        sections = [
            {
                "title": "시작하기",
                "content": "왼쪽에서 순서, 조건, 반복 템플릿 중 하나를 누르면 블록 워크스페이스가 바로 채워집니다.",
                "display_order": 1,
                "badge_text": "Step 1",
            },
            {
                "title": "블록과 코드 보기",
                "content": "블록을 이동하거나 연결하면 하단 코드 창과 오른쪽 상태 카드가 함께 갱신됩니다.",
                "display_order": 2,
                "badge_text": "Step 2",
            },
            {
                "title": "저장과 다시 불러오기",
                "content": "JSON 저장으로 현재 워크스페이스를 보관하고, 활동판 저장 (.svg)으로 수업 자료 이미지를 바로 내려받을 수 있습니다.",
                "display_order": 3,
                "badge_text": "Tip",
            },
        ]
        for section in sections:
            ManualSection.objects.get_or_create(
                manual=manual,
                title=section["title"],
                defaults={
                    "content": section["content"],
                    "display_order": section["display_order"],
                    "badge_text": section["badge_text"],
                },
            )

        self.stdout.write(self.style.SUCCESS("[ensure_blockclass] Done"))
