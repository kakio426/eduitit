from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure noticegen product exists in database"

    def handle(self, *args, **options):
        title = "알림장 & 주간학습 멘트 생성기"
        defaults = {
            "lead_text": "대상과 주제를 고르면, 교실에서 바로 쓸 수 있는 멘트를 빠르게 만듭니다.",
            "description": (
                "교사가 대상(저학년/고학년/학부모), 주제, 전달사항만 입력하면 "
                "즉시 사용할 수 있는 알림장 멘트를 생성합니다. "
                "유사 행사 캐시 재사용으로 반복 작업과 API 비용을 줄입니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": True,
            "icon": "📝",
            "color_theme": "blue",
            "card_size": "small",
            "display_order": 28,
            "service_type": "work",
            "external_url": "",
            "launch_route_name": "noticegen:main",
        }
        mutable_fields = [
            "lead_text",
            "description",
            "price",
            "is_guest_allowed",
            "icon",
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
                "icon": "🎯",
                "title": "대상별 문구 분기",
                "description": "저학년/고학년/학부모 버전 중 원하는 대상을 직접 선택해 생성합니다.",
            },
            {
                "icon": "⚡",
                "title": "즉시 생성",
                "description": "주제와 전달사항만 입력하면 2~3줄 멘트를 바로 만들어 줍니다.",
            },
            {
                "icon": "♻️",
                "title": "유사 행사 캐시 재사용",
                "description": "이전에 만든 유사 문구를 재활용해 반복 입력과 API 비용을 줄입니다.",
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
                "title": "알림장 멘트 생성기 사용 가이드",
                "description": "대상 선택부터 멘트 복사까지 바로 따라갈 수 있습니다.",
                "is_published": True,
            },
        )

        manual_changed = []
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        if manual.description != "대상 선택부터 멘트 복사까지 바로 따라갈 수 있습니다.":
            manual.description = "대상 선택부터 멘트 복사까지 바로 따라갈 수 있습니다."
            manual_changed.append("description")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        sections = [
            (
                "시작하기",
                "대상과 주제를 먼저 고른 뒤 전달사항을 입력하고 생성 버튼을 누르세요.",
                1,
            ),
            (
                "대상 선택 팁",
                "저학년은 쉬운 어휘, 고학년은 명확한 안내, 학부모는 공손한 안내로 자동 규칙이 적용됩니다.",
                2,
            ),
            (
                "비용 절감 팁",
                "유사한 행사 문구는 캐시를 재사용합니다. 전달사항을 조금 수정하면 새 문구를 생성할 수 있습니다.",
                3,
            ),
        ]
        for section_title, content, order in sections:
            section, created_section = ManualSection.objects.get_or_create(
                manual=manual,
                title=section_title,
                defaults={
                    "content": content,
                    "display_order": order,
                },
            )
            if not created_section:
                changed = []
                if section.content != content:
                    section.content = content
                    changed.append("content")
                if section.display_order != order:
                    section.display_order = order
                    changed.append("display_order")
                if changed:
                    section.save(update_fields=changed)

        self.stdout.write(self.style.SUCCESS("ensure_noticegen completed"))
