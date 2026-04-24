from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure PDF 작업실 product and manual exist in database"

    PRODUCT_TITLE = "PDF 작업실"
    LAUNCH_ROUTE = "pdfhub:main"

    def handle(self, *args, **options):
        defaults = {
            "lead_text": "PDF 작업을 목적별로 고릅니다.",
            "description": "PDF 보기, 사인, 동의서, 교과서 작업을 한곳에서 고릅니다.",
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "fa-solid fa-file-pdf",
            "color_theme": "red",
            "card_size": "small",
            "display_order": 18,
            "service_type": "work",
            "external_url": "",
            "launch_route_name": self.LAUNCH_ROUTE,
            "solve_text": "PDF 작업 바로 찾기",
            "result_text": "기존 PDF 서비스 연결",
            "time_text": "10초",
        }

        product = Product.objects.filter(launch_route_name=self.LAUNCH_ROUTE).order_by("id").first()
        if product is None:
            product = Product.objects.filter(title=self.PRODUCT_TITLE).order_by("id").first()

        created = product is None
        if product is None:
            product = Product.objects.create(title=self.PRODUCT_TITLE, **defaults)
        else:
            changed_fields = []
            if product.title != self.PRODUCT_TITLE:
                product.title = self.PRODUCT_TITLE
                changed_fields.append("title")
            for field_name, expected in defaults.items():
                if getattr(product, field_name) != expected:
                    setattr(product, field_name, expected)
                    changed_fields.append(field_name)
            if changed_fields:
                product.save(update_fields=list(dict.fromkeys(changed_fields)))

        features = [
            ("fa-solid fa-table-cells-large", "목적별 선택", "보기, 사인, 동의서, 교과서를 바로 고릅니다."),
            ("fa-solid fa-link", "기존 서비스 연결", "새 처리 없이 기존 PDF 서비스로 이동합니다."),
            ("fa-solid fa-hourglass-half", "다음 기능 준비", "합치기, 나누기, 압축은 후보로 둡니다."),
        ]
        for icon, title, description in features:
            ProductFeature.objects.update_or_create(
                product=product,
                title=title,
                defaults={"icon": icon, "description": description},
            )

        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": "PDF 작업실 사용 가이드",
                "description": "목적을 고르고 기존 서비스로 이동합니다.",
                "is_published": True,
            },
        )
        manual_updates = []
        if manual.title != "PDF 작업실 사용 가이드":
            manual.title = "PDF 작업실 사용 가이드"
            manual_updates.append("title")
        if manual.description != "목적을 고르고 기존 서비스로 이동합니다.":
            manual.description = "목적을 고르고 기존 서비스로 이동합니다."
            manual_updates.append("description")
        if not manual.is_published:
            manual.is_published = True
            manual_updates.append("is_published")
        if manual_updates:
            manual.save(update_fields=manual_updates)

        sections = [
            ("보기", "PDF는 보기에서 확인합니다.", 1, "핵심"),
            ("사인·동의서", "서명과 동의서 수합은 각 서비스로 이동합니다.", 2, "수합"),
            ("수업·분석", "교과서 수업과 PDF 분석은 보조 작업에서 엽니다.", 3, "수업"),
        ]
        for title, content, order, badge_text in sections:
            ManualSection.objects.update_or_create(
                manual=manual,
                title=title,
                defaults={
                    "content": content,
                    "display_order": order,
                    "badge_text": badge_text,
                },
            )

        label = "Created" if created else "Ensured"
        self.stdout.write(self.style.SUCCESS(f"[OK] {label} PDF 작업실 product (ID: {product.id})"))
