from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure 수업 QR 생성기 product exists in database"

    def handle(self, *args, **options):
        title = "수업 QR 생성기"
        defaults = {
            "lead_text": "모둠별 QR코드를 한 번에 만들고, 제목과 전환 간격을 정해 자동 순환으로 보여주세요.",
            "description": (
                "수업 자료 링크를 모둠별로 입력하면 여러 QR코드를 한 화면에서 만들 수 있습니다. "
                "자동 전환 화면에서는 교사가 설정한 초 단위로 QR이 넘어가며, 모둠 제목이 함께 표시되어 "
                "학생들이 자신의 QR을 빠르게 인식할 수 있습니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": True,
            "icon": "🔳",
            "color_theme": "blue",
            "card_size": "small",
            "display_order": 28,
            "service_type": "classroom",
            "external_url": "",
            "launch_route_name": "qrgen:landing",
            "solve_text": "모둠마다 다른 링크를 헷갈리지 않게 배포하고 싶어요",
            "result_text": "모둠 제목이 붙은 순환 QR 화면",
            "time_text": "30초",
        }
        mutable_fields = [
            "lead_text",
            "description",
            "price",
            "is_active",
            "is_guest_allowed",
            "icon",
            "external_url",
            "launch_route_name",
            "solve_text",
            "result_text",
            "time_text",
        ]

        product, created = Product.objects.get_or_create(
            title=title,
            defaults=defaults,
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f"Created product: {product.title}"))
        else:
            changed = []
            for field in mutable_fields:
                new_value = defaults[field]
                if getattr(product, field) != new_value:
                    setattr(product, field, new_value)
                    changed.append(field)
            if changed:
                product.save(update_fields=changed)
                self.stdout.write(self.style.SUCCESS(f"Updated product fields: {', '.join(changed)}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"Product already exists: {product.title}"))

        # Legacy title normalization without hard-coded old labels.
        for feature in ProductFeature.objects.filter(product=product):
            if feature.title.startswith("제목 표시") and feature.title.endswith("모드"):
                feature.title = "제목 표시 QR 화면"
                feature.save(update_fields=["title"])

        features = [
            {
                "icon": "🧩",
                "title": "모둠별 다중 QR 생성",
                "description": "여러 모둠의 제목과 링크를 입력해 QR코드를 한 번에 생성합니다.",
            },
            {
                "icon": "⏱️",
                "title": "초 단위 자동 순환",
                "description": "교사가 설정한 전환 간격에 맞춰 다음 모둠 QR로 자동 이동합니다.",
            },
            {
                "icon": "🖥️",
                "title": "제목 표시 QR 화면",
                "description": "현재 QR 상단에 모둠 제목을 크게 보여 학생들이 자신의 코드를 쉽게 찾습니다.",
            },
        ]
        for item in features:
            feature = ProductFeature.objects.filter(product=product, title=item["title"]).order_by("id").first()
            if feature is None:
                ProductFeature.objects.create(
                    product=product,
                    title=item["title"],
                    icon=item["icon"],
                    description=item["description"],
                )
                continue

            changed = []
            if feature.title != item["title"]:
                feature.title = item["title"]
                changed.append("title")
            if feature.icon != item["icon"]:
                feature.icon = item["icon"]
                changed.append("icon")
            if feature.description != item["description"]:
                feature.description = item["description"]
                changed.append("description")
            if changed:
                feature.save(update_fields=changed)

        target_manual_description = "모둠별 QR 생성부터 자동 순환 QR 화면까지 빠르게 사용하는 방법입니다."
        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": "수업 QR 생성기 사용법",
                "description": target_manual_description,
                "is_published": True,
            },
        )

        manual_changed = []
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        if manual.description != target_manual_description:
            manual.description = target_manual_description
            manual_changed.append("description")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        for section in ManualSection.objects.filter(manual=manual):
            if section.title.startswith("자동 순환") and section.title != "자동 순환 표시":
                section.title = "자동 순환 표시"
                section.save(update_fields=["title"])

        sections = [
            (
                "모둠 설정",
                "모둠별 제목과 링크를 입력하면 QR코드가 즉시 생성됩니다. http/https 링크만 지원합니다.",
                1,
            ),
            (
                "자동 순환 표시",
                "전환 간격(초)을 정한 뒤 자동 전환을 시작하면 모둠 QR이 자동으로 넘어갑니다.",
                2,
            ),
            (
                "현장 활용 팁",
                "모둠 제목을 실제 자리 배치와 동일하게 입력하면 학생 이동 동선을 줄일 수 있습니다.",
                3,
            ),
        ]
        for section_title, content, order in sections:
            section = ManualSection.objects.filter(manual=manual, title=section_title).order_by("id").first()
            if section is None:
                ManualSection.objects.create(
                    manual=manual,
                    title=section_title,
                    content=content,
                    display_order=order,
                )
                continue

            changed = []
            if section.title != section_title:
                section.title = section_title
                changed.append("title")
            if section.display_order != order:
                section.display_order = order
                changed.append("display_order")
            if section.content != content:
                section.content = content
                changed.append("content")
            if changed:
                section.save(update_fields=changed)

        self.stdout.write(self.style.SUCCESS("ensure_qrgen completed"))
