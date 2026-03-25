from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


SERVICE_TITLE = "초간단 PPT 만들기"
LEGACY_SERVICE_TITLES = ("수업 발표 메이커",)
SERVICE_MANUAL_TITLE = "초간단 PPT 만들기 사용 가이드"
SERVICE_MANUAL_DESCRIPTION = "발표 제목 입력부터 새 탭 발표 화면 열기까지 빠르게 익히는 안내입니다."


class Command(BaseCommand):
    help = "Ensure slidesmith product and manual exist in database"

    def handle(self, *args, **options):
        title = SERVICE_TITLE
        defaults = {
            "lead_text": "제목과 발표 내용을 적으면 바로 발표할 수 있는 슬라이드 흐름을 만들어 줍니다.",
            "description": (
                "학부모 설명회, 수업 안내, 교내 협의 자료처럼 교사가 빠르게 설명 자료를 정리할 때 쓰는 발표 도구입니다. "
                "편집 화면에서 슬라이드 흐름을 확인하고, 새 탭 발표 화면으로 바로 이어갈 수 있습니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "🪄",
            "color_theme": "blue",
            "card_size": "small",
            "display_order": 26,
            "service_type": "work",
            "external_url": "",
            "launch_route_name": "slidesmith:main",
            "solve_text": "설명 자료를 빠르게 띄우고 싶어요",
            "result_text": "발표용 슬라이드 화면",
            "time_text": "3분",
        }
        product = Product.objects.filter(title=title).first()
        created = False
        if product is None:
            for legacy_title in LEGACY_SERVICE_TITLES:
                product = Product.objects.filter(title=legacy_title).first()
                if product:
                    break

        if product is None:
            product = Product.objects.create(title=title, **defaults)
            created = True

        if created:
            self.stdout.write(self.style.SUCCESS("[ensure_slidesmith] Product created"))
        else:
            changed_fields = []
            if product.title != title:
                product.title = title
                changed_fields.append("title")
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
                        f"[ensure_slidesmith] Product fields updated: {', '.join(changed_fields)}"
                    )
                )

        features = [
            {
                "icon": "🧭",
                "title": "발표 흐름 바로 정리",
                "description": "슬라이드 구분선으로 설명 순서를 빠르게 나누고 표지까지 자동으로 붙입니다.",
            },
            {
                "icon": "👀",
                "title": "오른쪽 즉시 미리보기",
                "description": "편집하면서 슬라이드 수와 첫 장, 다음 행동을 바로 확인할 수 있습니다.",
            },
            {
                "icon": "🖥️",
                "title": "새 탭 발표 화면",
                "description": "입력한 내용을 reveal.js 발표 화면으로 열어 방향키로 바로 설명할 수 있습니다.",
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
                "title": SERVICE_MANUAL_TITLE,
                "description": SERVICE_MANUAL_DESCRIPTION,
                "is_published": True,
            },
        )

        manual_changed = []
        if manual.title != SERVICE_MANUAL_TITLE:
            manual.title = SERVICE_MANUAL_TITLE
            manual_changed.append("title")
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        if not (manual.description or "").strip():
            manual.description = SERVICE_MANUAL_DESCRIPTION
            manual_changed.append("description")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        sections = [
            {
                "title": "시작하기",
                "content": "발표 제목을 적고, 본문은 슬라이드마다 `---`로 구분해 주세요. 첫 줄은 슬라이드 제목으로 사용됩니다.",
                "display_order": 1,
                "badge_text": "Step 1",
            },
            {
                "title": "미리보기 확인",
                "content": "오른쪽 카드에서 표지 포함 슬라이드 수, 첫 슬라이드, 다음 행동을 바로 확인하세요. JavaScript가 켜져 있으면 입력과 동시에 갱신됩니다.",
                "display_order": 2,
                "badge_text": "Step 2",
            },
            {
                "title": "발표 시작과 PDF 저장",
                "content": "발표 시작 (새 탭) 버튼으로 reveal.js 화면을 열고 방향키로 발표하세요. 필요하면 브라우저 인쇄 기능으로 PDF 저장까지 이어갈 수 있습니다.",
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

        self.stdout.write(self.style.SUCCESS("[ensure_slidesmith] Done"))
