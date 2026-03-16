from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure messagebox product and manual exist in database"

    PRODUCT_TITLE = "업무 메시지 보관함"
    LAUNCH_ROUTE = "messagebox:main"

    def handle(self, *args, **options):
        defaults = {
            "lead_text": "메신저에서 받은 중요한 메시지를 붙여넣고, 나중에 다시 보거나 일정에 연결합니다.",
            "description": (
                "업무 메시지 보관함은 교육청 메신저나 메모 앱에서 받은 중요한 내용을 복사해 붙여넣고, "
                "필요하면 날짜를 먼저 적어 둔 뒤 나중에 다시 보거나 학급 캘린더 일정과 연결하는 서비스입니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "🗂️",
            "color_theme": "orange",
            "card_size": "small",
            "display_order": 16,
            "service_type": "classroom",
            "external_url": "",
            "launch_route_name": self.LAUNCH_ROUTE,
            "solve_text": "나중에 꼭 처리해야 할 메시지를 놓치지 않고 싶어요",
            "result_text": "다시 볼 메시지 보관함 + 캘린더 연결",
            "time_text": "1분",
        }

        product = Product.objects.filter(launch_route_name=self.LAUNCH_ROUTE).order_by("id").first()
        if not product:
            product = Product.objects.filter(title=self.PRODUCT_TITLE).order_by("id").first()

        if product is None:
            product = Product.objects.create(title=self.PRODUCT_TITLE, **defaults)
            self.stdout.write(self.style.SUCCESS(f"Created product: {product.title}"))
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
                        f"Updated product essentials: {', '.join(dict.fromkeys(changed_fields))}"
                    )
                )
            else:
                self.stdout.write(self.style.SUCCESS(f"Product already exists: {product.title}"))

        feature_specs = [
            {
                "icon": "📋",
                "title": "메시지 붙여넣기",
                "description": "교육청 메신저나 메모 앱에서 받은 내용을 그대로 붙여넣고 바로 보관할 수 있습니다.",
            },
            {
                "icon": "📅",
                "title": "날짜 먼저 적어두기",
                "description": "정확한 일정 연결 전에도 날짜를 먼저 정해 두고 다시 볼 메시지로 남길 수 있습니다.",
            },
            {
                "icon": "🔗",
                "title": "학급 캘린더 연결",
                "description": "다시 볼 시점이 분명해지면 캘린더 일정이나 할 일과 연결해 업무 흐름을 이어갑니다.",
            },
        ]
        for item in feature_specs:
            ProductFeature.objects.update_or_create(
                product=product,
                title=item["title"],
                defaults={
                    "icon": item["icon"],
                    "description": item["description"],
                },
            )

        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": "업무 메시지 보관함 시작 가이드",
                "description": "메시지 붙여넣기부터 보관, 날짜 연결, 처리 완료까지 바로 따라갈 수 있습니다.",
                "is_published": True,
            },
        )
        manual_changed = []
        if manual.title != "업무 메시지 보관함 시작 가이드":
            manual.title = "업무 메시지 보관함 시작 가이드"
            manual_changed.append("title")
        if manual.description != "메시지 붙여넣기부터 보관, 날짜 연결, 처리 완료까지 바로 따라갈 수 있습니다.":
            manual.description = "메시지 붙여넣기부터 보관, 날짜 연결, 처리 완료까지 바로 따라갈 수 있습니다."
            manual_changed.append("description")
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        section_specs = [
            ("메시지 보관", "메신저에서 받은 내용을 붙여넣고 필요하면 날짜와 한 줄 메모를 적어 보관합니다.", 1),
            ("날짜 연결", "보관한 메시지에서 날짜 후보를 확인한 뒤 학급 캘린더 일정이나 할 일과 연결합니다.", 2),
            ("처리 완료", "이미 처리한 메시지는 완료로 바꿔 보관함에서 다시 볼 메시지와 구분합니다.", 3),
        ]
        for title, content, display_order in section_specs:
            ManualSection.objects.update_or_create(
                manual=manual,
                title=title,
                defaults={
                    "content": content,
                    "display_order": display_order,
                },
            )

        self.stdout.write(self.style.SUCCESS("ensure_messagebox completed"))
