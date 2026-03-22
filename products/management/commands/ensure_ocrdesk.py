from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


SERVICE_TITLE = "사진 글자 읽기"
SERVICE_ROUTE = "ocrdesk:main"


class Command(BaseCommand):
    help = "Ensure ocrdesk product exists in database"

    def handle(self, *args, **options):
        defaults = {
            "lead_text": "사진 한 장만 올리면 읽은 글자를 바로 고치고 복사할 수 있습니다.",
            "description": (
                "칠판, 안내문, 프린트 사진을 올리면 읽은 원문 텍스트를 바로 보여 줍니다. "
                "자동 요약이나 문장 변환 없이 원문 그대로 편집해 쓸 수 있습니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "📷",
            "color_theme": "blue",
            "card_size": "small",
            "display_order": 33,
            "service_type": "work",
            "external_url": "",
            "launch_route_name": SERVICE_ROUTE,
            "solve_text": "칠판 사진에서 글자를 바로 뽑아요",
            "result_text": "편집 가능한 원문 텍스트",
            "time_text": "1분",
        }
        enforced_fields = {
            "launch_route_name": SERVICE_ROUTE,
            "service_type": "work",
            "is_guest_allowed": False,
            "external_url": "",
        }
        backfill_only_fields = [
            "lead_text",
            "description",
            "price",
            "icon",
            "solve_text",
            "result_text",
            "time_text",
        ]

        product = Product.objects.filter(launch_route_name=SERVICE_ROUTE).first()
        if product is None:
            product = Product.objects.filter(title=SERVICE_TITLE).first()

        if product is None:
            product = Product.objects.create(title=SERVICE_TITLE, **defaults)
            self.stdout.write(self.style.SUCCESS(f"Created product: {product.title}"))
        else:
            changed = []
            for field, new_value in enforced_fields.items():
                if getattr(product, field) != new_value:
                    setattr(product, field, new_value)
                    changed.append(field)
            for field in backfill_only_fields:
                current_value = getattr(product, field)
                if current_value not in ("", None):
                    continue
                new_value = defaults[field]
                if current_value != new_value:
                    setattr(product, field, new_value)
                    changed.append(field)
            if changed:
                product.save(update_fields=changed)
                self.stdout.write(self.style.SUCCESS(f"Updated product fields: {', '.join(changed)}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"Product already exists: {product.title}"))

        feature_specs = [
            {
                "icon": "🖼️",
                "title": "사진 1장 바로 읽기",
                "description": "칠판이나 안내문 사진 한 장만 올리면 바로 글자를 읽습니다.",
            },
            {
                "icon": "✍️",
                "title": "편집 가능한 원문",
                "description": "자동으로 다듬지 않은 원문 텍스트를 textarea로 바로 보여 줍니다.",
            },
            {
                "icon": "🧹",
                "title": "읽고 바로 지움",
                "description": "업로드한 사진과 결과를 저장하지 않고 처리 후 바로 지웁니다.",
            },
        ]

        existing_features = list(ProductFeature.objects.filter(product=product).order_by("id"))
        for index, item in enumerate(feature_specs):
            if index < len(existing_features):
                feature = existing_features[index]
                changed = []
                if not feature.icon:
                    feature.icon = item["icon"]
                    changed.append("icon")
                if not feature.title:
                    feature.title = item["title"]
                    changed.append("title")
                if not feature.description:
                    feature.description = item["description"]
                    changed.append("description")
                if changed:
                    feature.save(update_fields=changed)
                continue
            ProductFeature.objects.create(
                product=product,
                icon=item["icon"],
                title=item["title"],
                description=item["description"],
            )

        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": "사진 글자 읽기 사용 가이드",
                "description": "사진 고르기부터 결과 복사까지 바로 따라할 수 있습니다.",
                "is_published": True,
            },
        )

        manual_changed = []
        if not manual.title:
            manual.title = "사진 글자 읽기 사용 가이드"
            manual_changed.append("title")
        if not manual.description:
            manual.description = "사진 고르기부터 결과 복사까지 바로 따라할 수 있습니다."
            manual_changed.append("description")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        sections = [
            (
                "시작하기",
                "사진 선택을 누르고 칠판이나 안내문 사진 1장을 고른 뒤 글자 읽기를 누르세요.",
                1,
            ),
            (
                "잘 읽히는 사진",
                "글씨가 화면에 크게 보이고 흔들리지 않은 사진이 잘 읽힙니다. 칠판 반사나 먼 거리 촬영은 정확도가 떨어질 수 있습니다.",
                2,
            ),
            (
                "결과 활용",
                "읽은 글자는 자동으로 다듬지 않습니다. 필요한 부분만 직접 고친 뒤 복사해서 알림장이나 문서에 붙여 넣으세요.",
                3,
            ),
        ]
        existing_sections = list(manual.sections.order_by("display_order", "id"))
        next_display_order = max([section.display_order for section in existing_sections], default=0)
        for index, (section_title, content, _order) in enumerate(sections):
            if index < len(existing_sections):
                section = existing_sections[index]
                changed = []
                if not section.title:
                    section.title = section_title
                    changed.append("title")
                if not section.content:
                    section.content = content
                    changed.append("content")
                if changed:
                    section.save(update_fields=changed)
                continue
            next_display_order += 1
            ManualSection.objects.create(
                manual=manual,
                title=section_title,
                content=content,
                display_order=next_display_order,
            )

        self.stdout.write(self.style.SUCCESS("ensure_ocrdesk completed"))
