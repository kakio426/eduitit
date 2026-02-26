from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure parentcomm product and manual exist in database"

    def handle(self, *args, **options):
        title = "학부모 소통 허브"
        defaults = {
            "lead_text": "채팅 과몰입 없이, 꼭 필요한 소통만 구조화해 학부모와 안전하게 연결합니다.",
            "description": (
                "쪽지형 커뮤니케이션과 상담 조율 흐름을 기반으로, "
                "교사가 채팅/전화/방문 상담 방식을 선택해 제안할 수 있습니다. "
                "긴급 상황은 20자 이내의 짧은 안내로만 접수되어 스트레스성 장문 메시지를 줄입니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "📨",
            "color_theme": "blue",
            "card_size": "small",
            "display_order": 35,
            "service_type": "counsel",
            "external_url": "",
            "launch_route_name": "parentcomm:main",
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
                "icon": "✉️",
                "title": "끊어 읽는 소통",
                "description": "메신저 과몰입 대신 스레드형 메시지로 필요한 대화만 남기고 관리합니다.",
            },
            {
                "icon": "🧭",
                "title": "상담 방식 제안",
                "description": "교사가 상황별로 채팅상담, 전화상담, 방문상담 중 가능한 방식을 골라 제안합니다.",
            },
            {
                "icon": "🚨",
                "title": "긴급 안내 20자 제한",
                "description": "지각/결석/조퇴 같은 긴급 상황은 20자 이내 짧은 안내만 접수합니다.",
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
                "title": "학부모 소통 허브 사용 가이드",
                "description": "쪽지형 소통, 상담 조율, 긴급 안내 흐름을 단계별로 안내합니다.",
                "is_published": True,
            },
        )

        manual_changed = []
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        expected_description = "쪽지형 소통, 상담 조율, 긴급 안내 흐름을 단계별로 안내합니다."
        if manual.description != expected_description:
            manual.description = expected_description
            manual_changed.append("description")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        section_specs = [
            (
                "시작하기",
                "학부모 연락처를 등록한 뒤, 연락처별 긴급안내 링크를 공유하면 즉시 소통을 시작할 수 있습니다.",
                1,
            ),
            (
                "상담 조율",
                "교사가 상담 요청별로 채팅/전화/방문 중 가능한 방식을 선택해 제안하고, 시간 슬롯을 등록해 조율합니다.",
                2,
            ),
            (
                "긴급 안내 규칙",
                "긴급 알림은 지각/결석/조퇴 중심의 20자 이내 짧은 문장으로만 접수되어 과도한 장문 민원을 예방합니다.",
                3,
            ),
        ]
        for section_title, content, order in section_specs:
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

        self.stdout.write(self.style.SUCCESS("ensure_parentcomm completed"))

