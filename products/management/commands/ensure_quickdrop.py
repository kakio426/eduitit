from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure quickdrop product and manual exist in database"

    PRODUCT_TITLE = "바로전송"
    LAUNCH_ROUTE = "quickdrop:landing"
    ADMIN_MANAGED_FIELDS = {"service_type", "display_order", "color_theme", "card_size"}

    def handle(self, *args, **options):
        create_defaults = {
            "lead_text": "처음 한 번만 로그인해 두면 내 기기끼리 텍스트나 이미지를 바로 옮깁니다.",
            "description": (
                "바로전송은 교사 기기에서 처음 한 번만 로그인해 개인 전용 통로를 만들고, 다른 기기는 한 번만 연결해 둔 뒤 텍스트 붙여넣기나 사진 선택만으로 "
                "다른 기기에 바로 띄우는 임시 전송 서비스입니다. 전송을 마치면 내용은 바로 지워지고 기기 연결만 남습니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "⚡",
            "color_theme": "blue",
            "card_size": "small",
            "display_order": 17,
            "service_type": "classroom",
            "external_url": "",
            "launch_route_name": self.LAUNCH_ROUTE,
            "solve_text": "내 폰과 PC 사이에 텍스트나 이미지를 바로 옮기고 싶어요",
            "result_text": "개인 전용 즉시 전송 통로",
            "time_text": "10초",
        }
        sync_defaults = {
            field_name: value
            for field_name, value in create_defaults.items()
            if field_name not in self.ADMIN_MANAGED_FIELDS
        }

        product = Product.objects.filter(launch_route_name=self.LAUNCH_ROUTE).order_by("id").first()
        if not product:
            product = Product.objects.filter(title=self.PRODUCT_TITLE).order_by("id").first()

        if product is None:
            product = Product.objects.create(title=self.PRODUCT_TITLE, **create_defaults)
            self.stdout.write(self.style.SUCCESS(f"Created product: {product.title}"))
        else:
            changed_fields = []
            for field_name, value in sync_defaults.items():
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
                "title": "붙여넣기 즉시 전송",
                "description": "데스크톱에서는 화면 어디서든 붙여넣기만 해도 최신 텍스트가 바로 바뀝니다.",
            },
            {
                "icon": "🖼️",
                "title": "사진 한 장 바로 교체",
                "description": "사진을 선택하거나 클립보드 이미지를 붙여넣으면 최신 이미지 1장만 남겨 가볍게 전송합니다.",
            },
            {
                "icon": "🧹",
                "title": "끝내면 바로 삭제",
                "description": "내용 지우기를 누르거나 10분 동안 멈추면 텍스트와 이미지는 바로 지워져 보관 부담이 남지 않습니다.",
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
                "title": "바로전송 사용 가이드",
                "description": "처음 연결부터 텍스트 전송, 사진 전송까지 바로 따라갈 수 있습니다.",
                "is_published": True,
            },
        )
        manual_changed = []
        if manual.title != "바로전송 사용 가이드":
            manual.title = "바로전송 사용 가이드"
            manual_changed.append("title")
        if manual.description != "처음 연결부터 텍스트 전송, 사진 전송까지 바로 따라갈 수 있습니다.":
            manual.description = "처음 연결부터 텍스트 전송, 사진 전송까지 바로 따라갈 수 있습니다."
            manual_changed.append("description")
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        section_specs = [
            ("처음 연결", "교사 기기에서는 처음 한 번 로그인해 통로를 만들고, 새 기기에서는 QR을 한 번만 스캔해 등록합니다.", 1),
            ("텍스트 보내기", "데스크톱은 붙여넣기만, 모바일은 입력칸에 붙여넣고 보내기만 누르면 됩니다.", 2),
            ("사진 보내기", "사진 선택 또는 클립보드 이미지 붙여넣기로 최신 이미지 1장만 바로 바뀝니다.", 3),
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

        self.stdout.write(self.style.SUCCESS("ensure_quickdrop completed"))
