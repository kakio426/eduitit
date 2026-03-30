from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure TTS announcement product and manual exist in database"

    PRODUCT_TITLE = "교실 방송 TTS"
    LAUNCH_ROUTE = "tts_announce"

    def handle(self, *args, **options):
        defaults = {
            "lead_text": "학생들에게 지금 필요한 말을 직접 쓰고 바로 읽을 수 있습니다.",
            "description": (
                "교사가 학생들에게 들려줄 안내 문구를 직접 입력하고, 자주 쓰는 방송 문구를 불러오고, "
                "필요하면 오늘 시간표 기준 교시 안내까지 가져와 브라우저 TTS로 바로 읽는 서비스입니다."
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
            "solve_text": "학생들에게 지금 필요한 말을 바로 읽어 주고 싶어요",
            "result_text": "학급 방송 문구",
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
                "title": "직접 입력해 바로 읽기",
                "description": "지금 필요한 방송 문구를 바로 고쳐 쓰고 학생들에게 곧바로 읽어 줄 수 있습니다.",
            },
            {
                "icon": "🔊",
                "title": "학생 대상 빠른 문구",
                "description": "수업 시작, 집중 요청, 정리 안내처럼 자주 쓰는 방송 문구를 한 번에 불러옵니다.",
            },
            {
                "icon": "📋",
                "title": "시간표 안내도 함께",
                "description": "교시 안내가 필요하면 오늘 시간표 기준 문구도 바로 가져와 읽거나 복사할 수 있습니다.",
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
                "title": "교실 방송 TTS 시작 가이드",
                "description": "직접 입력, 빠른 문구, 시간표 안내 가져오기 흐름을 바로 따라갈 수 있습니다.",
                "is_published": True,
            },
        )

        manual_changed = []
        if manual.title != "교실 방송 TTS 시작 가이드":
            manual.title = "교실 방송 TTS 시작 가이드"
            manual_changed.append("title")
        if manual.description != "직접 입력, 빠른 문구, 시간표 안내 가져오기 흐름을 바로 따라갈 수 있습니다.":
            manual.description = "직접 입력, 빠른 문구, 시간표 안내 가져오기 흐름을 바로 따라갈 수 있습니다."
            manual_changed.append("description")
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        section_specs = [
            ("직접 입력해서 읽기", "큰 입력창에 지금 필요한 말을 바로 쓰고 읽기 버튼으로 학생들에게 들려줄 수 있습니다.", 1),
            ("빠른 문구 가져오기", "수업 시작, 집중 요청, 정리 안내 같은 자주 쓰는 방송 문구를 한 번에 불러옵니다.", 2),
            ("시간표 안내 함께 쓰기", "교시 안내가 필요하면 오늘 시간표 기반 문구도 아래 보조 목록에서 바로 가져와 씁니다.", 3),
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
