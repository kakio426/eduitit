from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure handoff product and manual exist in database"

    def handle(self, *args, **options):
        product = (
            Product.objects.filter(launch_route_name="handoff:landing").first()
            or Product.objects.filter(title="배부 체크").first()
        )

        if product is None:
            product = Product.objects.create(
                title="배부 체크",
                lead_text="명단을 저장해두고, 배부할 때 누가 가져갔는지 빠르게 체크하세요.",
                description="배부 세션을 만들면 미수령자 중심 화면에서 체크를 빠르게 진행할 수 있습니다. 체크 결과는 세션별로 저장되며 미수령자 안내문 복사와 CSV 내보내기도 지원합니다.",
                price=0.00,
                is_active=True,
                is_guest_allowed=False,
                icon="📦",
                color_theme="blue",
                card_size="small",
                display_order=36,
                service_type="work",
                external_url="",
                launch_route_name="handoff:landing",
                solve_text="배부 누락 확인을 빠르게 끝내고 싶어요",
                result_text="세션별 수령 현황표",
                time_text="2분",
            )
            self.stdout.write(self.style.SUCCESS(f"[OK] Created product: {product.title}"))
        else:
            changed = []
            if not product.is_active:
                product.is_active = True
                changed.append("is_active")
            if (product.launch_route_name or "").strip() != "handoff:landing":
                product.launch_route_name = "handoff:landing"
                changed.append("launch_route_name")
            if (product.external_url or "").strip():
                product.external_url = ""
                changed.append("external_url")
            if changed:
                product.save(update_fields=changed)
                self.stdout.write(self.style.SUCCESS(f"[OK] Updated product essentials: {product.title}"))

        feature_specs = [
            {
                "title": "미수령자 중심 체크",
                "description": "체크하면 목록에서 빠져 배부자가 남은 인원만 집중해서 볼 수 있습니다.",
                "icon": "✅",
            },
            {
                "title": "명단 재사용",
                "description": "명단을 저장해두고 배부 세션만 새로 만들어 반복 업무를 줄입니다.",
                "icon": "📋",
            },
            {
                "title": "결과 내보내기",
                "description": "미수령자 안내문 복사와 CSV 내보내기로 후속 조치까지 한 번에 처리합니다.",
                "icon": "📤",
            },
        ]
        for spec in feature_specs:
            feature, _ = ProductFeature.objects.get_or_create(
                product=product,
                title=spec["title"],
                defaults={
                    "description": spec["description"],
                    "icon": spec["icon"],
                },
            )
            update_fields = []
            if feature.description != spec["description"]:
                feature.description = spec["description"]
                update_fields.append("description")
            if feature.icon != spec["icon"]:
                feature.icon = spec["icon"]
                update_fields.append("icon")
            if update_fields:
                feature.save(update_fields=update_fields)

        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": "배부 체크 사용법",
                "description": "명단 등록부터 수령 확인까지 빠르게 시작하는 방법입니다.",
                "is_published": True,
            },
        )

        manual_updates = []
        if not manual.is_published:
            manual.is_published = True
            manual_updates.append("is_published")
        if manual.title != "배부 체크 사용법":
            manual.title = "배부 체크 사용법"
            manual_updates.append("title")
        if manual.description != "명단 등록부터 수령 확인까지 빠르게 시작하는 방법입니다.":
            manual.description = "명단 등록부터 수령 확인까지 빠르게 시작하는 방법입니다."
            manual_updates.append("description")
        if manual_updates:
            manual.save(update_fields=manual_updates)

        section_specs = [
            (
                "시작하기",
                "1) 명단을 만들고 멤버를 등록합니다.\n2) 배부 세션을 생성합니다.\n3) 체크 화면에서 수령 여부를 확인합니다.",
                1,
            ),
            (
                "핵심 기능",
                "- 미수령자 중심 화면\n- 이름/초성 검색\n- 세션 마감 및 다시 열기",
                2,
            ),
            (
                "후속 조치",
                "미수령 안내문 복사, CSV 내보내기로 안내와 기록 정리를 마무리하세요.",
                3,
            ),
        ]
        for title, content, order in section_specs:
            section, _ = ManualSection.objects.get_or_create(
                manual=manual,
                title=title,
                defaults={"content": content, "display_order": order},
            )
            changed = []
            if section.content != content:
                section.content = content
                changed.append("content")
            if section.display_order != order:
                section.display_order = order
                changed.append("display_order")
            if changed:
                section.save(update_fields=changed)

        self.stdout.write(self.style.SUCCESS("[OK] ensure_handoff complete"))
