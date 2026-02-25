from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure timetable product exists in database"

    def handle(self, *args, **options):
        title = "전담 시간표·특별실 배치 도우미"
        defaults = {
            "lead_text": "전담 수업을 먼저 맞추고, 겹침 없는 시간표와 특별실 운영표를 빠르게 준비하세요.",
            "description": (
                "전담 선생님 배정표를 올리면 겹침을 먼저 점검하고, "
                "학교 상황에 맞게 특별실을 자동배치 또는 예약연동 방식으로 관리할 수 있습니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": True,
            "icon": "🗓️",
            "color_theme": "blue",
            "card_size": "small",
            "display_order": 35,
            "service_type": "work",
            "external_url": "",
            "launch_route_name": "timetable:main",
        }
        mutable_fields = [
            "lead_text",
            "description",
            "price",
            "is_active",
            "is_guest_allowed",
            "icon",
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
                "icon": "✅",
                "title": "겹침 없는 전담 시간표",
                "description": "전담 선생님과 학급 시간칸이 겹치지 않도록 먼저 점검합니다.",
            },
            {
                "icon": "🏫",
                "title": "특별실 운영 방식 선택",
                "description": "특별실별로 자동배치 또는 예약연동 운영을 나눠 설정할 수 있습니다.",
            },
            {
                "icon": "📄",
                "title": "교사용 엑셀 양식 점검",
                "description": "입력 항목 누락과 형식을 업로드 단계에서 먼저 확인해 오류를 줄입니다.",
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
                "title": "전담 시간표·특별실 배치 도우미 사용 가이드",
                "description": "입력 양식 준비부터 점검, 특별실 운영 연결까지 단계별로 안내합니다.",
                "is_published": True,
            },
        )

        manual_changed = []
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        manual_desc = "입력 양식 준비부터 점검, 특별실 운영 연결까지 단계별로 안내합니다."
        if manual.description != manual_desc:
            manual.description = manual_desc
            manual_changed.append("description")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        sections = [
            (
                "시작하기",
                "엑셀 양식을 내려받아 필수 시트 이름과 항목명을 바꾸지 않고 입력해 주세요.",
                1,
            ),
            (
                "입력 점검하기",
                "작성한 파일을 업로드하면 누락 항목과 형식 오류를 먼저 점검해 알려드립니다.",
                2,
            ),
            (
                "특별실 운영 연결",
                "특별실마다 자동배치 또는 예약연동을 선택하고 미리보기 후 반영할 수 있습니다.",
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

        self.stdout.write(self.style.SUCCESS("ensure_timetable completed"))
