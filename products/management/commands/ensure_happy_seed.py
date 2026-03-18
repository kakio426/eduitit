from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure 행복의 씨앗 product exists in database"

    def handle(self, *args, **options):
        title = "행복의 씨앗"
        defaults = {
            "lead_text": "작은 실천을 씨앗으로, 교실의 성장을 꽃으로 연결하세요.",
            "description": (
                "행복의 씨앗은 초등 교실의 긍정 행동을 기록하고, "
                "씨앗-꽃피움 흐름으로 동기를 설계하는 학급 운영 서비스입니다. "
                "보호자 동의, 보상 확률 설정, 공개 꽃밭까지 한 번에 관리할 수 있습니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": True,
            "icon": "🌱",
            "color_theme": "green",
            "card_size": "small",
            "display_order": 27,
            "service_type": "classroom",
            "external_url": "",
            "launch_route_name": "happy_seed:dashboard",
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

        feature_specs = [
            {
                "icon": "🌸",
                "title": "꽃피움 추첨 보상",
                "legacy_titles": ["꽃피움 랜덤 보상"],
                "description": "성실 참여와 우수 성취를 바탕으로 공평한 추첨 보상을 운영합니다.",
            },
            {
                "icon": "🏡",
                "title": "학급 꽃밭 대시보드",
                "legacy_titles": ["학급 꽃밭"],
                "description": "교실 화면에서 아이들과 함께 성장 흐름을 시각적으로 확인할 수 있습니다.",
            },
            {
                "icon": "🌱",
                "title": "긍정 행동 기록",
                "legacy_titles": ["교사 분석"],
                "description": "학생의 작은 실천을 씨앗으로 쌓아, 참여 습관 형성을 돕습니다.",
            },
        ]

        for item in feature_specs:
            titles = [item["title"], *item.get("legacy_titles", [])]
            feature = ProductFeature.objects.filter(product=product, title__in=titles).order_by("id").first()
            if feature is None:
                ProductFeature.objects.create(
                    product=product,
                    title=item["title"],
                    icon=item["icon"],
                    description=item["description"],
                )
                self.stdout.write(self.style.SUCCESS(f"  Added feature: {item['title']}"))
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
                self.stdout.write(self.style.SUCCESS(f"  Updated feature: {item['title']} ({', '.join(changed)})"))

        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": "행복의 씨앗 시작 가이드",
                "description": "교실 생성부터 동의 관리, 씨앗·꽃피움 운영까지 바로 따라갈 수 있습니다.",
                "is_published": True,
            },
        )

        manual_changed = []
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        target_manual_description = "교실 생성부터 동의 관리, 씨앗·꽃피움 운영까지 바로 따라갈 수 있습니다."
        if manual.description != target_manual_description:
            manual.description = target_manual_description
            manual_changed.append("description")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        sections = [
            (
                "시작하기",
                (
                    "1) 교실 생성 -> 2) 학생 등록 -> 3) 동의 관리에서 서명톡 링크 생성 순서로 시작합니다. "
                    "보호자 동의가 완료된 학생만 기록 저장 및 보상 지급이 가능합니다."
                ),
                1,
            ),
            (
                "주요 기능",
                (
                    "성실 참여/우수 성취 티켓 부여, 미당첨 씨앗 +1, 씨앗 N개 자동 티켓 전환, "
                    "꽃피움 추첨과 축하 화면 운영 흐름을 제공합니다."
                ),
                2,
            ),
            (
                "보상 확률 설정",
                (
                    "보상마다 선택 확률(%)을 설정할 수 있습니다. "
                    "해당 값은 '당첨 발생 시 어떤 보상을 줄지'를 정하는 상대 가중치로 동작합니다."
                ),
                3,
            ),
            (
                "동의 운영",
                (
                    "동의 관리 화면에서 서명톡 링크를 생성하면 학생 동의 항목에 자동 반영됩니다. "
                    "링크 공유 후 제출 현황을 확인해 동의완료 상태로 전환하세요."
                ),
                4,
            ),
            (
                "사용 팁",
                "비교 대신 행동 언어를 사용하고, 축하 장면은 교사가 직접 마무리해 주세요.",
                5,
            ),
        ]
        for section_title, content, order in sections:
            section, section_created = ManualSection.objects.get_or_create(
                manual=manual,
                title=section_title,
                defaults={"content": content, "display_order": order},
            )
            if not section_created:
                changed = []
                if section.display_order != order:
                    section.display_order = order
                    changed.append("display_order")
                if section.content != content:
                    section.content = content
                    changed.append("content")
                if changed:
                    section.save(update_fields=changed)

        self.stdout.write(self.style.SUCCESS("ensure_happy_seed completed"))
