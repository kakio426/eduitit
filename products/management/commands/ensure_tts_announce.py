from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure TTS announcement product and manual exist in database"

    PRODUCT_TITLE = "교시 안내 TTS"
    LAUNCH_ROUTE = "tts_announce"

    def handle(self, *args, **options):
        defaults = {
            "lead_text": "교시별 안내 문구를 바로 읽고, 복사해서 교실 방송에 쓸 수 있습니다.",
            "description": (
                "교시 시작 5분 전에 읽을 문구를 자동으로 만들고, 브라우저 TTS로 읽거나 복사해서 "
                "교실 방송과 메신저에 바로 붙여 넣는 서비스입니다. 저장된 시간표가 없으면 샘플 문구로 바로 시험할 수 있습니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": True,
            "icon": "📣",
            "color_theme": "orange",
            "card_size": "small",
            "display_order": 17,
            "service_type": "classroom",
            "external_url": "",
            "launch_route_name": self.LAUNCH_ROUTE,
            "solve_text": "교시 전에 방송할 문구를 빠르게 만들고 싶어요",
            "result_text": "교시별 안내 문구",
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
                "icon": "🧭",
                "title": "교시별 문구 자동 생성",
                "description": "1교시, 2교시처럼 교시 번호와 과목을 묶어 바로 읽을 안내 문구를 만듭니다.",
            },
            {
                "icon": "🔊",
                "title": "브라우저 음성 재생",
                "description": "한국어 음성을 선택해 바로 읽고, 필요할 때는 중지할 수 있습니다.",
            },
            {
                "icon": "📋",
                "title": "복사해서 바로 방송",
                "description": "읽기 전에 문구를 복사해 교실 방송, 메신저, 게시판에 붙여 넣을 수 있습니다.",
            },
        ]

        for item in feature_specs:
            feature, created_feature = ProductFeature.objects.get_or_create(
                product=product,
                title=item["title"],
                defaults={
                    "icon": item["icon"],
                    "description": item["description"],
                },
            )
            if not created_feature:
                changed = []
                if feature.icon != item["icon"]:
                    feature.icon = item["icon"]
                    changed.append("icon")
                if feature.description != item["description"]:
                    feature.description = item["description"]
                    changed.append("description")
                if changed:
                    feature.save(update_fields=changed)

        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": "교시 안내 TTS 시작 가이드",
                "description": "오늘 시간표를 불러오고, 문구를 읽고, 복사하는 흐름을 바로 따라갈 수 있습니다.",
                "is_published": True,
            },
        )

        manual_changed = []
        if manual.title != "교시 안내 TTS 시작 가이드":
            manual.title = "교시 안내 TTS 시작 가이드"
            manual_changed.append("title")
        if manual.description != "오늘 시간표를 불러오고, 문구를 읽고, 복사하는 흐름을 바로 따라갈 수 있습니다.":
            manual.description = "오늘 시간표를 불러오고, 문구를 읽고, 복사하는 흐름을 바로 따라갈 수 있습니다."
            manual_changed.append("description")
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        section_specs = [
            ("오늘 시간표 불러오기", "저장된 시간표가 있으면 오늘 교시 목록을 보여 주고, 없으면 샘플 문구로 바로 시험할 수 있습니다.", 1),
            ("읽기와 중지", "목소리, 속도, 높이를 고른 뒤 읽기를 누르면 브라우저 TTS가 안내 문구를 읽습니다.", 2),
            ("복사해서 바로 방송", "문구를 복사해 교실 방송이나 메신저에 붙여 넣고, 필요하면 직접 고쳐서 사용합니다.", 3),
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

        self.stdout.write(self.style.SUCCESS("ensure_tts_announce completed"))
