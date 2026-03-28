from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure edu_materials_next product and manual exist in database"

    PRODUCT_TITLE = "AI 자료실 Next"
    LAUNCH_ROUTE = "edu_materials_next:main"

    def handle(self, *args, **options):
        defaults = {
            "lead_text": "처음 배우기, 예시 리믹스, QR 배포까지 한 흐름으로 줄인 비교용 신버전입니다.",
            "description": (
                "AI 자료실 Next는 초보 교사가 바이브코딩으로 수업용 HTML 자료를 만들고, 검증된 스타터로 시작하고, "
                "QR 전체화면으로 바로 배포하도록 다시 설계한 비교용 신버전입니다. 기존 서비스와 데이터를 섞지 않고 "
                "필요할 때만 old 자료를 복사해 가져와 비교할 수 있습니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": True,
            "is_guest_allowed": False,
            "icon": "🧭",
            "color_theme": "green",
            "card_size": "small",
            "display_order": 17,
            "service_type": "classroom",
            "external_url": "",
            "launch_route_name": self.LAUNCH_ROUTE,
            "solve_text": "초보 교사용 인터랙티브 수업자료를 더 짧은 흐름으로 만들고 싶어요",
            "result_text": "스타터 기반 HTML 자료와 QR 배포",
            "time_text": "3분",
        }

        product = Product.objects.filter(launch_route_name=self.LAUNCH_ROUTE).order_by("id").first()
        if product is None:
            product = Product.objects.create(title=self.PRODUCT_TITLE, **defaults)
            self.stdout.write(self.style.SUCCESS("[ensure_edu_materials_next] Product created"))
        else:
            changed_fields = []
            for field_name, value in defaults.items():
                if getattr(product, field_name) != value:
                    setattr(product, field_name, value)
                    changed_fields.append(field_name)
            if product.title != self.PRODUCT_TITLE:
                product.title = self.PRODUCT_TITLE
                changed_fields.append("title")
            if changed_fields:
                product.save(update_fields=list(dict.fromkeys(changed_fields)))
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[ensure_edu_materials_next] Product fields updated: {', '.join(dict.fromkeys(changed_fields))}"
                    )
                )

        features = [
            {
                "icon": "🧩",
                "title": "처음 배우기 위저드",
                "description": "주제 입력, 안내문 복사, HTML 저장까지 한 화면의 세로 흐름으로 이어집니다.",
            },
            {
                "icon": "🗂️",
                "title": "검증된 스타터 리믹스",
                "description": "추천 학년과 수업 시간, 바꿔 볼 포인트 3개가 붙은 스타터로 바로 시작합니다.",
            },
            {
                "icon": "📺",
                "title": "QR 전체화면 우선",
                "description": "상세 화면의 주 액션을 QR 전체화면으로 고정해 교실 배포를 더 짧게 만듭니다.",
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
                "title": "AI 자료실 Next 사용 가이드",
                "description": "처음 배우기부터 예시 리믹스, QR 배포까지 비교용 신버전 흐름을 빠르게 익히는 안내입니다.",
                "is_published": True,
            },
        )
        manual_changed = []
        if manual.title != "AI 자료실 Next 사용 가이드":
            manual.title = "AI 자료실 Next 사용 가이드"
            manual_changed.append("title")
        if manual.description != "처음 배우기부터 예시 리믹스, QR 배포까지 비교용 신버전 흐름을 빠르게 익히는 안내입니다.":
            manual.description = "처음 배우기부터 예시 리믹스, QR 배포까지 비교용 신버전 흐름을 빠르게 익히는 안내입니다."
            manual_changed.append("description")
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        sections = [
            {
                "title": "처음 배우기",
                "content": "주제를 적고 안내문을 복사한 뒤, AI가 만든 HTML 전체를 붙여넣으면 바로 시작판이 열립니다.",
                "display_order": 1,
                "badge_text": "Step 1",
            },
            {
                "title": "예시 리믹스",
                "content": "스타터 카드에서 추천 학년, 수업 시간, 바꿔 볼 포인트를 보고 바로 리믹스 흐름으로 넘어갑니다.",
                "display_order": 2,
                "badge_text": "Step 2",
            },
            {
                "title": "QR 배포",
                "content": "상세 화면에서는 QR 전체화면이 주 액션이며, 학생은 QR 또는 6자리 코드로 즉시 입장합니다.",
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

        self.stdout.write(self.style.SUCCESS("[ensure_edu_materials_next] Done"))
