from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure textbook_ai product and manual exist in database"

    PRODUCT_TITLE = "PDF 분석 도우미"
    LAUNCH_ROUTE = "textbook_ai:main"

    def handle(self, *args, **options):
        defaults = {
            "lead_text": "PDF를 AI가 읽기 좋은 형태로 정리해 검색과 확인이 쉬워집니다.",
            "description": (
                "PDF 분석 도우미는 디지털 PDF를 로컬 파서로 읽어 목차, 본문, 표, 페이지 근거를 구조화하는 서비스입니다. "
                "외부 생성 비용을 먼저 쓰지 않고, PDF를 믿고 읽고 찾을 수 있는 상태로 만드는 데 집중합니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": True,
            "is_guest_allowed": False,
            "icon": "🗂️",
            "color_theme": "green",
            "card_size": "small",
            "display_order": 17,
            "service_type": "work",
            "external_url": "",
            "launch_route_name": self.LAUNCH_ROUTE,
            "solve_text": "PDF를 AI가 읽기 좋게 정리하고 싶어요",
            "result_text": "검색 가능한 구조화 PDF",
            "time_text": "2분",
        }

        product = Product.objects.filter(launch_route_name=self.LAUNCH_ROUTE).order_by("id").first()
        if not product:
            product = Product.objects.filter(title=self.PRODUCT_TITLE).order_by("id").first()

        if product is None:
            product = Product.objects.create(title=self.PRODUCT_TITLE, **defaults)
            self.stdout.write(self.style.SUCCESS("[ensure_textbook_ai] Product created"))
        else:
            changed_fields = []
            admin_managed_fields = {"is_active", "color_theme", "display_order"}
            for field_name, value in defaults.items():
                if field_name in admin_managed_fields:
                    continue
                if getattr(product, field_name) != value:
                    setattr(product, field_name, value)
                    changed_fields.append(field_name)
            if product.title != self.PRODUCT_TITLE:
                product.title = self.PRODUCT_TITLE
                changed_fields.append("title")
            valid_service_types = {code for code, _ in Product.SERVICE_CHOICES}
            if product.service_type not in valid_service_types:
                product.service_type = defaults["service_type"]
                changed_fields.append("service_type")
            valid_color_themes = {code for code, _ in Product.COLOR_CHOICES}
            if product.color_theme not in valid_color_themes:
                product.color_theme = defaults["color_theme"]
                changed_fields.append("color_theme")
            if changed_fields:
                product.save(update_fields=list(dict.fromkeys(changed_fields)))
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[ensure_textbook_ai] Product fields updated: {', '.join(dict.fromkeys(changed_fields))}"
                    )
                )

        features = [
            {
                "icon": "📄",
                "title": "PDF 구조화",
                "description": "디지털 PDF를 읽어 목차, 본문, 표를 구조화하고 저장합니다.",
            },
            {
                "icon": "🔎",
                "title": "페이지 근거 검색",
                "description": "찾은 내용마다 페이지 근거를 함께 보여줘 다시 확인하기 쉽습니다.",
            },
            {
                "icon": "💸",
                "title": "비용 통제형 시작",
                "description": "v1은 외부 LLM 없이 읽기 품질과 검색 가능한 구조에 집중합니다.",
            },
        ]
        for feature in features:
            ProductFeature.objects.update_or_create(
                product=product,
                title=feature["title"],
                defaults={
                    "icon": feature["icon"],
                    "description": feature["description"],
                },
            )

        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": "PDF 분석 도우미 사용 가이드",
                "description": "PDF 올리기부터 구조 확인, 검색까지 빠르게 따라가는 안내입니다.",
                "is_published": True,
            },
        )
        manual_changed = []
        if not (manual.title or "").strip():
            manual.title = "PDF 분석 도우미 사용 가이드"
            manual_changed.append("title")
        if not (manual.description or "").strip():
            manual.description = "PDF 올리기부터 구조 확인, 검색까지 빠르게 따라가는 안내입니다."
            manual_changed.append("description")
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        sections = [
            {
                "title": "PDF 올리기",
                "content": "자료 제목과 과목을 적고 PDF를 올리면 로컬 파서가 구조를 정리합니다.",
                "display_order": 1,
                "badge_text": "Step 1",
            },
            {
                "title": "구조 확인",
                "content": "상세 화면에서 목차, 본문 미리보기, 표 미리보기를 먼저 확인해 주세요.",
                "display_order": 2,
                "badge_text": "Step 2",
            },
            {
                "title": "검색 활용",
                "content": "검색 탭에서 필요한 내용을 찾고, 페이지 근거와 함께 원본 PDF를 다시 열 수 있습니다.",
                "display_order": 3,
                "badge_text": "Step 3",
            },
        ]
        for section in sections:
            ManualSection.objects.update_or_create(
                manual=manual,
                title=section["title"],
                defaults={
                    "content": section["content"],
                    "display_order": section["display_order"],
                    "badge_text": section["badge_text"],
                },
            )

        self.stdout.write(self.style.SUCCESS("[ensure_textbook_ai] Done"))
