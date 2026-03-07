from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure docviewer product and manual exist in database"

    def handle(self, *args, **options):
        title = "문서 미리보기실"
        defaults = {
            "lead_text": "PDF를 올리면 같은 화면에서 바로 넘겨 보고 확인할 수 있어요.",
            "description": (
                "가정통신문, 회의 자료, 연수 자료처럼 PDF 문서를 빠르게 검수할 때 쓰는 교사용 미리보기 도구입니다. "
                "브라우저 안에서 페이지 이동과 확대/축소를 바로 하고, 인쇄용 새 탭도 즉시 열 수 있습니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "📑",
            "color_theme": "blue",
            "card_size": "small",
            "display_order": 25,
            "service_type": "work",
            "external_url": "",
            "launch_route_name": "docviewer:main",
            "solve_text": "PDF를 빠르게 미리보기 하고 싶어요",
            "result_text": "브라우저 PDF 검수 화면",
            "time_text": "1분",
        }
        product, created = Product.objects.get_or_create(title=title, defaults=defaults)

        if created:
            self.stdout.write(self.style.SUCCESS("[ensure_docviewer] Product created"))
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
                        f"[ensure_docviewer] Product fields updated: {', '.join(changed_fields)}"
                    )
                )

        features = [
            {
                "icon": "📄",
                "title": "PDF 바로 열기",
                "description": "파일을 선택하면 첫 페이지를 같은 화면에서 바로 렌더링합니다.",
            },
            {
                "icon": "🔎",
                "title": "빠른 검수 조작",
                "description": "페이지 이동과 확대/축소를 한 자리에서 바로 처리할 수 있습니다.",
            },
            {
                "icon": "🖨️",
                "title": "인쇄용 새 탭",
                "description": "검수가 끝나면 인쇄용 새 탭을 열어 브라우저 인쇄로 바로 이어집니다.",
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
                "description": "PDF 선택부터 빠른 검수, 인쇄용 새 탭 열기까지 빠르게 익히는 안내입니다.",
                "is_published": True,
            },
        )

        manual_changed = []
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        if not (manual.description or "").strip():
            manual.description = "PDF 선택부터 빠른 검수, 인쇄용 새 탭 열기까지 빠르게 익히는 안내입니다."
            manual_changed.append("description")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        sections = [
            {
                "title": "시작하기",
                "content": "왼쪽에서 PDF를 선택하면 오른쪽 미리보기 화면이 바로 열립니다. 서버 저장 없이 브라우저에서만 미리보기 합니다.",
                "display_order": 1,
                "badge_text": "Step 1",
            },
            {
                "title": "빠른 검수",
                "content": "이전 쪽, 다음 쪽, 확대, 축소 버튼으로 필요한 부분만 바로 확인하세요. 현재 쪽수와 확대 비율이 화면에 함께 표시됩니다.",
                "display_order": 2,
                "badge_text": "Step 2",
            },
            {
                "title": "다음 행동",
                "content": "검수가 끝나면 인쇄하기 (새 탭) 버튼으로 브라우저 인쇄 화면으로 이어지고, 다른 PDF 고르기로 바로 다음 문서를 확인할 수 있습니다.",
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

        self.stdout.write(self.style.SUCCESS("[ensure_docviewer] Done"))
