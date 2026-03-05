from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure sheetbook product and manual exist in database"

    PRODUCT_TITLE = "교무수첩"
    LAUNCH_ROUTE = "sheetbook:index"

    def handle(self, *args, **options):
        product = Product.objects.filter(launch_route_name=self.LAUNCH_ROUTE).first()
        if not product:
            product = Product.objects.filter(title=self.PRODUCT_TITLE).first()

        if product is None:
            product = Product.objects.create(
                title=self.PRODUCT_TITLE,
                lead_text="복사·붙여넣기 중심으로 학급 운영 기록을 한 곳에 정리하세요.",
                description=(
                    "교무수첩은 일정, 명부, 메모를 한 화면에서 관리하고 필요할 때 "
                    "간편 수합·동의서·안내문으로 바로 연결해 주는 교사 작업공간입니다."
                ),
                price=0.00,
                is_active=True,
                is_featured=True,
                is_guest_allowed=False,
                icon="📒",
                color_theme="blue",
                card_size="small",
                display_order=12,
                service_type="classroom",
                external_url="",
                launch_route_name=self.LAUNCH_ROUTE,
            )
            self.stdout.write(self.style.SUCCESS(f"Created product: {product.title}"))
        else:
            updated_fields = []
            if product.title != self.PRODUCT_TITLE:
                product.title = self.PRODUCT_TITLE
                updated_fields.append("title")
            if product.launch_route_name != self.LAUNCH_ROUTE:
                product.launch_route_name = self.LAUNCH_ROUTE
                updated_fields.append("launch_route_name")
            if product.icon != "📒":
                product.icon = "📒"
                updated_fields.append("icon")
            if not product.is_active:
                product.is_active = True
                updated_fields.append("is_active")
            if product.external_url:
                product.external_url = ""
                updated_fields.append("external_url")
            if updated_fields:
                product.save(update_fields=updated_fields)
                self.stdout.write(
                    self.style.SUCCESS(f"Updated product essentials: {', '.join(updated_fields)}")
                )
            else:
                self.stdout.write(self.style.SUCCESS(f"Product already exists: {product.title}"))

        feature_specs = [
            {
                "icon": "📋",
                "title": "복사·붙여넣기 중심 입력",
                "description": "구글시트처럼 붙여넣어 빠르게 일정과 명단을 채울 수 있어요.",
            },
            {
                "icon": "📅",
                "title": "달력 탭 바로 연동",
                "description": "일정 탭의 날짜를 달력으로 옮겨 오늘 할 일을 한눈에 확인합니다.",
            },
            {
                "icon": "⚡",
                "title": "수업 도구 즉시 실행",
                "description": "선택한 칸에서 간편 수합, 동의서, 안내문을 바로 시작할 수 있어요.",
            },
        ]
        for item in feature_specs:
            feature, created = ProductFeature.objects.get_or_create(
                product=product,
                title=item["title"],
                defaults={
                    "icon": item["icon"],
                    "description": item["description"],
                },
            )
            if created:
                continue
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
                "title": "교무수첩 사용 가이드",
                "description": "첫 수첩 만들기부터 연동 기능 활용까지 순서대로 안내합니다.",
                "is_published": True,
            },
        )
        manual_updates = []
        if manual.title != "교무수첩 사용 가이드":
            manual.title = "교무수첩 사용 가이드"
            manual_updates.append("title")
        if manual.description != "첫 수첩 만들기부터 연동 기능 활용까지 순서대로 안내합니다.":
            manual.description = "첫 수첩 만들기부터 연동 기능 활용까지 순서대로 안내합니다."
            manual_updates.append("description")
        if not manual.is_published:
            manual.is_published = True
            manual_updates.append("is_published")
        if manual_updates:
            manual.save(update_fields=manual_updates)

        section_specs = [
            (
                "시작하기",
                "교무수첩에서 새 수첩을 만들고 기본 탭(달력/일정/학생명부/메모)을 바로 사용해 보세요.",
                1,
            ),
            (
                "빠른 입력",
                "기존 시트 내용을 복사해 붙여넣으면 여러 칸이 한 번에 입력됩니다.",
                2,
            ),
            (
                "수업 연동",
                "선택한 칸에서 간편 수합, 동의서, 안내문을 바로 실행해 업무를 이어갈 수 있어요.",
                3,
            ),
        ]
        for title, content, display_order in section_specs:
            section, created = ManualSection.objects.get_or_create(
                manual=manual,
                title=title,
                defaults={
                    "content": content,
                    "display_order": display_order,
                },
            )
            if created:
                continue
            changed = []
            if section.content != content:
                section.content = content
                changed.append("content")
            if section.display_order != display_order:
                section.display_order = display_order
                changed.append("display_order")
            if changed:
                section.save(update_fields=changed)

        self.stdout.write(self.style.SUCCESS("ensure_sheetbook completed"))
