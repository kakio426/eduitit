from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


SERVICE_TITLE = "함께문서실"
LAUNCH_ROUTE = "doccollab:main"
MANUAL_TITLE = "함께문서실 사용 가이드"
MANUAL_DESCRIPTION = "HWP 또는 HWPX 업로드부터 함께 편집, 저장, 공식본 지정까지 빠르게 시작하는 방법입니다."


class Command(BaseCommand):
    help = "Ensure doccollab product and manual exist in database"

    def handle(self, *args, **options):
        defaults = {
            "lead_text": "HWP와 HWPX 문서를 열고 같이 쓰고 버전까지 남깁니다.",
            "description": (
                "함께문서실은 HWP와 HWPX 문서를 데스크톱 Chrome에서 함께 열어 작업하고, "
                "협업 저장본과 공식본을 나눠 관리하는 문서 허브입니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "📝",
            "color_theme": "green",
            "card_size": "small",
            "display_order": 25,
            "service_type": "work",
            "external_url": "",
            "launch_route_name": LAUNCH_ROUTE,
            "solve_text": "한 문서를 같이 고칩니다",
            "result_text": "협업 저장본과 공식본",
            "time_text": "10분 안팎",
        }
        product = Product.objects.filter(launch_route_name=LAUNCH_ROUTE).order_by("id").first()
        if product is None:
            product = Product.objects.create(title=SERVICE_TITLE, **defaults)
            self.stdout.write(self.style.SUCCESS("[OK] Created doccollab product."))
        else:
            changed = []
            if product.title != SERVICE_TITLE:
                product.title = SERVICE_TITLE
                changed.append("title")
            for field, value in defaults.items():
                if getattr(product, field) != value:
                    setattr(product, field, value)
                    changed.append(field)
            if changed:
                product.save(update_fields=changed)
                self.stdout.write(self.style.SUCCESS(f"[OK] Updated doccollab fields: {', '.join(changed)}"))

        features = [
            {
                "icon": "📂",
                "title": "오늘 작업",
                "description": "내 문서, 공유 문서, 최근 저장본을 한 화면에서 확인합니다.",
            },
            {
                "icon": "👥",
                "title": "같이 편집",
                "description": "데스크톱 Chrome에서 같은 문서를 열고 변경을 바로 반영합니다.",
            },
            {
                "icon": "💾",
                "title": "저장과 공식본",
                "description": "협업 저장본을 HWP로 쌓고, 필요한 시점에 공식본으로 따로 지정합니다.",
            },
        ]
        feature_titles = {item["title"] for item in features}
        for item in features:
            feature, _created = ProductFeature.objects.get_or_create(
                product=product,
                title=item["title"],
                defaults={"icon": item["icon"], "description": item["description"]},
            )
            changed = []
            if feature.icon != item["icon"]:
                feature.icon = item["icon"]
                changed.append("icon")
            if feature.description != item["description"]:
                feature.description = item["description"]
                changed.append("description")
            if changed:
                feature.save(update_fields=changed)
        ProductFeature.objects.filter(product=product).exclude(title__in=feature_titles).delete()

        manual, _created = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": MANUAL_TITLE,
                "description": MANUAL_DESCRIPTION,
                "is_published": True,
            },
        )
        manual_changed = []
        if manual.title != MANUAL_TITLE:
            manual.title = MANUAL_TITLE
            manual_changed.append("title")
        if manual.description != MANUAL_DESCRIPTION:
            manual.description = MANUAL_DESCRIPTION
            manual_changed.append("description")
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        sections = [
            {
                "title": "시작",
                "content": "HWP 또는 HWPX 파일을 올리면 문서방이 바로 만들어집니다. 원본은 그대로 남고, 협업 저장본은 따로 쌓입니다.",
                "layout_type": "text_only",
                "display_order": 1,
                "badge_text": "Step 1",
            },
            {
                "title": "같이 쓰기",
                "content": "데스크톱 Chrome에서 문서를 열고, 공유할 선생님을 추가해 함께 수정합니다.",
                "layout_type": "text_only",
                "display_order": 2,
                "badge_text": "Step 2",
            },
            {
                "title": "저장",
                "content": "협업 저장본을 HWP로 내보내고, 필요한 시점에 공식본으로 지정해 내려받습니다.",
                "layout_type": "text_only",
                "display_order": 3,
                "badge_text": "Step 3",
            },
        ]
        section_titles = {item["title"] for item in sections}
        for item in sections:
            section, _created = ManualSection.objects.get_or_create(
                manual=manual,
                title=item["title"],
                defaults=item,
            )
            changed = []
            for field in ("content", "layout_type", "display_order", "badge_text"):
                if getattr(section, field) != item[field]:
                    setattr(section, field, item[field])
                    changed.append(field)
            if changed:
                section.save(update_fields=changed)
        manual.sections.exclude(title__in=section_titles).delete()
        self.stdout.write(self.style.SUCCESS("[OK] doccollab service ensured."))
