from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure tap reflex game product exists in database"

    def handle(self, *args, **options):
        title = "탭 순발력 챌린지"
        defaults = {
            "lead_text": "탭 신호를 보고 가장 빠르게 반응하는 교실용 반응속도 게임입니다.",
            "description": (
                "탭 순발력 챌린지는 랜덤 신호를 기다렸다가 정확한 타이밍에 화면을 터치해 반응속도를 측정하는 교실 활동입니다. "
                "싱글 기록 도전, 1:1 대결, 신호 전 터치 반칙 처리, 전체화면 모드를 지원합니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "⚡",
            "color_theme": "green",
            "card_size": "small",
            "display_order": 22,
            "service_type": "game",
            "external_url": "",
            "launch_route_name": "reflex_game:main",
        }
        mutable_fields = [
            "lead_text",
            "description",
            "price",
            "is_active",
            "is_featured",
            "is_guest_allowed",
            "icon",
            "color_theme",
            "card_size",
            "display_order",
            "service_type",
            "external_url",
            "launch_route_name",
        ]

        product, created = Product.objects.get_or_create(title=title, defaults=defaults)
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

        feature_specs = [
            {
                "icon": "⏱️",
                "title": "반응속도 측정",
                "description": "랜덤 신호 이후 탭 시간을 ms 단위로 표시합니다.",
            },
            {
                "icon": "🚫",
                "title": "반칙 감지",
                "description": "탭 사인 전에 누르면 반칙으로 즉시 표시됩니다.",
            },
            {
                "icon": "🖥️",
                "title": "전체화면 지원",
                "description": "교실 터치 스크린에서 몰입감 있게 진행할 수 있습니다.",
            },
        ]

        used_feature_ids = set()
        for item in feature_specs:
            feature = (
                ProductFeature.objects.filter(product=product, title=item["title"])
                .exclude(id__in=used_feature_ids)
                .order_by("id")
                .first()
            )
            if feature is None:
                feature = (
                    ProductFeature.objects.filter(product=product)
                    .exclude(id__in=used_feature_ids)
                    .order_by("id")
                    .first()
                )
            if feature is None:
                feature = ProductFeature.objects.create(
                    product=product,
                    icon=item["icon"],
                    title=item["title"],
                    description=item["description"],
                )
            else:
                changed = []
                if feature.icon != item["icon"]:
                    feature.icon = item["icon"]
                    changed.append("icon")
                if feature.title != item["title"]:
                    feature.title = item["title"]
                    changed.append("title")
                if feature.description != item["description"]:
                    feature.description = item["description"]
                    changed.append("description")
                if changed:
                    feature.save(update_fields=changed)
            used_feature_ids.add(feature.id)

        stale_features = ProductFeature.objects.filter(product=product).exclude(id__in=used_feature_ids)
        if stale_features.exists():
            stale_features.delete()

        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": "탭 순발력 챌린지 사용 가이드",
                "description": "시작, 반칙 규칙, 전체화면 활용을 바로 확인할 수 있습니다.",
                "is_published": True,
            },
        )

        manual_changed = []
        if manual.title != "탭 순발력 챌린지 사용 가이드":
            manual.title = "탭 순발력 챌린지 사용 가이드"
            manual_changed.append("title")
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        target_desc = "시작, 반칙 규칙, 전체화면 활용을 바로 확인할 수 있습니다."
        if manual.description != target_desc:
            manual.description = target_desc
            manual_changed.append("description")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        sections = [
            (
                "시작하기",
                "교실 활동에서 '탭 순발력 챌린지'를 누른 뒤 시작 버튼으로 게임을 시작합니다.",
                1,
            ),
            (
                "반칙 규칙",
                "탭 신호(TAP) 전에 화면을 누르면 즉시 반칙으로 처리되어 기록이 인정되지 않습니다.",
                2,
            ),
            (
                "대결 운영",
                "1:1 대결 모드에서 좌우 플레이어가 동시에 준비하고 신호 후 먼저 탭한 학생이 승리합니다.",
                3,
            ),
        ]
        used_section_ids = set()
        for section_title, content, order in sections:
            section = (
                ManualSection.objects.filter(manual=manual, title=section_title)
                .exclude(id__in=used_section_ids)
                .order_by("display_order", "id")
                .first()
            )
            if section is None:
                section = (
                    ManualSection.objects.filter(manual=manual, display_order=order)
                    .exclude(id__in=used_section_ids)
                    .order_by("id")
                    .first()
                )
            if section is None:
                section = ManualSection.objects.create(
                    manual=manual,
                    title=section_title,
                    content=content,
                    display_order=order,
                )
            else:
                changed = []
                if section.title != section_title:
                    section.title = section_title
                    changed.append("title")
                if section.content != content:
                    section.content = content
                    changed.append("content")
                if section.display_order != order:
                    section.display_order = order
                    changed.append("display_order")
                if changed:
                    section.save(update_fields=changed)
            used_section_ids.add(section.id)

        stale_sections = ManualSection.objects.filter(manual=manual).exclude(id__in=used_section_ids)
        if stale_sections.exists():
            stale_sections.delete()

        self.stdout.write(self.style.SUCCESS("ensure_reflex_game completed"))
