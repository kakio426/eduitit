from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure internal docviewer metadata and manual exist in database"

    def handle(self, *args, **options):
        title = "문서 미리보기실"
        defaults = {
            "lead_text": "동의서와 서명 같은 문서형 서비스 안에서 PDF를 안정적으로 보여 주는 내부 뷰어 기반입니다.",
            "description": (
                "동의서, 서명, 문서 검토 흐름 안에서 PDF를 같은 화면에서 안정적으로 렌더링하기 위한 내부 공용 뷰어입니다. "
                "교사용 메인 메뉴에 노출하지 않고, 각 서비스 화면 안에서 재사용하는 것을 기본으로 둡니다."
            ),
            "price": 0.00,
            "is_active": False,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "📑",
            "color_theme": "blue",
            "card_size": "small",
            "display_order": 25,
            "service_type": "work",
            "external_url": "",
            "launch_route_name": "docviewer:main",
            "solve_text": "서비스 안에서 PDF를 바로 보여 주고 싶어요",
            "result_text": "서비스 내 PDF 미리보기",
            "time_text": "1분",
        }
        product, created = Product.objects.get_or_create(title=title, defaults=defaults)

        if created:
            self.stdout.write(self.style.SUCCESS("[ensure_docviewer] Product created as internal-only"))
        else:
            changed_fields = []
            if product.is_active != defaults["is_active"]:
                product.is_active = defaults["is_active"]
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
                        f"[ensure_docviewer] Product fields updated: {', '.join(changed_fields)}"
                    )
                )

        features = [
            {
                "icon": "📄",
                "title": "서비스 내 PDF 렌더링",
                "description": "동의서와 서명 화면 안에서 PDF 첫 페이지와 전체 문서를 안정적으로 렌더링합니다.",
            },
            {
                "icon": "🔎",
                "title": "빠른 검수 조작",
                "description": "페이지 이동과 확대/축소를 서비스 흐름 안에서 바로 처리할 수 있습니다.",
            },
            {
                "icon": "🧩",
                "title": "공용 뷰어 기반",
                "description": "독립 서비스가 아니라 consent, signatures 같은 문서형 기능이 재사용하는 내부 기반입니다.",
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
                "title": "문서 미리보기실 사용 가이드",
                "description": "문서형 서비스 안에서 PDF 미리보기를 재사용할 때 참고하는 내부 안내입니다.",
                "is_published": True,
            },
        )

        manual_changed = []
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        if not (manual.description or "").strip():
            manual.description = "문서형 서비스 안에서 PDF 미리보기를 재사용할 때 참고하는 내부 안내입니다."
            manual_changed.append("description")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        sections = [
            {
                "title": "역할",
                "content": "문서 미리보기실은 독립 메뉴용 서비스가 아니라 consent, signatures 같은 문서형 기능이 PDF를 안정적으로 보여 주기 위한 내부 기반입니다.",
                "display_order": 1,
                "badge_text": "Internal",
            },
            {
                "title": "핵심 동작",
                "content": "서비스 화면 안에서 이전 쪽, 다음 쪽, 확대, 축소 같은 기본 검수 조작을 공통으로 재사용할 수 있습니다.",
                "display_order": 2,
                "badge_text": "Viewer",
            },
            {
                "title": "적용 대상",
                "content": "동의서, 서명, 문서 확인이 필요한 흐름에 우선 적용하고, 교사용 메인 홈 카드에는 노출하지 않습니다.",
                "display_order": 3,
                "badge_text": "Scope",
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

        self.stdout.write(self.style.SUCCESS("[ensure_docviewer] Done"))
