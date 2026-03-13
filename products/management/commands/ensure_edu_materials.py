from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure edu_materials product and manual exist in database"

    PRODUCT_TITLE = "교육 자료실"
    LAUNCH_ROUTE = "edu_materials:main"

    def handle(self, *args, **options):
        defaults = {
            "lead_text": "바이브코딩으로 만든 HTML 수업 자료를 붙여넣거나 파일로 올려 바로 실행합니다.",
            "description": (
                "교육 자료실은 바이브코딩 툴에서 만든 HTML 수업 자료를 보관하고, 학생에게 QR과 링크로 바로 열어줄 수 있는 서비스입니다. "
                "교사용 미리보기와 학생 실행 화면을 분리하고, 실행 화면은 sandbox iframe으로 안전하게 분리해 수업 화면을 오염시키지 않습니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": True,
            "is_guest_allowed": True,
            "icon": "🧩",
            "color_theme": "green",
            "card_size": "small",
            "display_order": 16,
            "service_type": "classroom",
            "external_url": "",
            "launch_route_name": self.LAUNCH_ROUTE,
            "solve_text": "바로 실행할 수 있는 HTML 수업 자료를 쓰고 싶어요",
            "result_text": "학생용 실행 링크와 QR",
            "time_text": "2분",
        }

        product = Product.objects.filter(launch_route_name=self.LAUNCH_ROUTE).order_by("id").first()
        if not product:
            product = Product.objects.filter(title=self.PRODUCT_TITLE).order_by("id").first()

        if product is None:
            product = Product.objects.create(title=self.PRODUCT_TITLE, **defaults)
            self.stdout.write(self.style.SUCCESS("[ensure_edu_materials] Product created"))
        else:
            changed_fields = []
            for field_name, value in defaults.items():
                if field_name == "is_active":
                    continue
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
                        f"[ensure_edu_materials] Product fields updated: {', '.join(dict.fromkeys(changed_fields))}"
                    )
                )

        features = [
            {
                "icon": "🧪",
                "title": "HTML 자료 바로 실행",
                "description": "붙여넣은 코드나 업로드한 HTML 파일을 저장 직후 같은 화면에서 실행해 확인합니다.",
            },
            {
                "icon": "🛡️",
                "title": "Sandbox 학생 화면",
                "description": "학생 실행 화면은 sandbox iframe으로 분리되어 호스트 페이지를 건드리지 않습니다.",
            },
            {
                "icon": "📎",
                "title": "QR 즉시 배포",
                "description": "공개를 켜면 학생 접속 주소와 QR을 바로 보여줘 수업에 즉시 붙일 수 있습니다.",
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
                "title": "교육 자료실 사용 가이드",
                "description": "HTML 자료 올리기부터 학생 공개, 수업 적용까지 빠르게 익히는 안내입니다.",
                "is_published": True,
            },
        )
        manual_changed = []
        if manual.title != "교육 자료실 사용 가이드":
            manual.title = "교육 자료실 사용 가이드"
            manual_changed.append("title")
        if manual.description != "HTML 자료 올리기부터 학생 공개, 수업 적용까지 빠르게 익히는 안내입니다.":
            manual.description = "HTML 자료 올리기부터 학생 공개, 수업 적용까지 빠르게 익히는 안내입니다."
            manual_changed.append("description")
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        sections = [
            {
                "title": "시작하기",
                "content": "HTML 코드를 붙여넣거나 `.html` 파일을 올리면 즉시 실행 가능한 교육 자료로 저장됩니다.",
                "display_order": 1,
                "badge_text": "Step 1",
            },
            {
                "title": "교사용 확인",
                "content": "상세 화면에서 sandbox iframe 미리보기로 자료가 의도한 대로 동작하는지 먼저 확인하세요.",
                "display_order": 2,
                "badge_text": "Step 2",
            },
            {
                "title": "학생 공개",
                "content": "공개를 켜면 학생용 실행 링크와 QR이 생성되고, 비공개 상태에서는 학생이 직접 접근할 수 없습니다.",
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

        self.stdout.write(self.style.SUCCESS("[ensure_edu_materials] Done"))
