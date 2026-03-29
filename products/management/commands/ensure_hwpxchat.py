from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


SERVICE_TITLE = "한글문서 AI야 읽어줘"
LEGACY_TITLES = ("한글 문서 톡톡", "HWPX 문서 AI 대화")

MANUAL_TITLE = "한글문서 AI야 읽어줘 사용 가이드"
LEGACY_MANUAL_TITLES = (
    "한글 문서 톡톡 사용 가이드",
    "HWPX 문서 AI 대화 사용 가이드",
)
MANUAL_DESCRIPTION = "공문 업로드부터 해야 할 일 카드 확인, 복사, 다시 묻기까지 빠르게 시작하는 방법입니다."


class Command(BaseCommand):
    help = "Ensure hwpxchat product and manual exist in database"

    def handle(self, *args, **options):
        product = Product.objects.filter(title=SERVICE_TITLE).first()

        if not product:
            for legacy_title in LEGACY_TITLES:
                legacy_product = Product.objects.filter(title=legacy_title).first()
                if not legacy_product:
                    continue

                legacy_product.title = SERVICE_TITLE
                update_fields = ["title"]
                if not legacy_product.launch_route_name:
                    legacy_product.launch_route_name = "hwpxchat:main"
                    update_fields.append("launch_route_name")
                legacy_product.save(update_fields=update_fields)
                product = legacy_product
                self.stdout.write(self.style.SUCCESS("[OK] Renamed legacy HWPX service title."))
                break

        if not product:
            product = Product.objects.create(
                title=SERVICE_TITLE,
                lead_text="공문이나 한글 문서를 올리면 해야 할 일, 기한, 전달 대상을 카드로 정리해 드려요.",
                description=(
                    "교사가 업로드한 HWPX 문서를 읽어 공문의 해야 할 일, 기한, 전달 대상을 실행 카드로 정리하고, "
                    "필요할 때 문서 근거를 다시 묻거나 원문 Markdown을 내려받을 수 있는 서비스입니다."
                ),
                price=0.00,
                is_active=True,
                is_featured=False,
                is_guest_allowed=False,
                icon="📄",
                color_theme="green",
                card_size="small",
                display_order=24,
                service_type="work",
                external_url="",
                launch_route_name="hwpxchat:main",
                solve_text="공문에서 해야 할 일을 바로 정리해요",
                result_text="실행용 업무 카드",
                time_text="1분",
            )
            self.stdout.write(self.style.SUCCESS("[OK] Created hwpxchat service product."))
        else:
            changed_fields = []
            if not product.launch_route_name:
                product.launch_route_name = "hwpxchat:main"
                changed_fields.append("launch_route_name")
            if product.lead_text != "공문이나 한글 문서를 올리면 해야 할 일, 기한, 전달 대상을 카드로 정리해 드려요.":
                product.lead_text = "공문이나 한글 문서를 올리면 해야 할 일, 기한, 전달 대상을 카드로 정리해 드려요."
                changed_fields.append("lead_text")
            expected_description = (
                "교사가 업로드한 HWPX 문서를 읽어 공문의 해야 할 일, 기한, 전달 대상을 실행 카드로 정리하고, "
                "필요할 때 문서 근거를 다시 묻거나 원문 Markdown을 내려받을 수 있는 서비스입니다."
            )
            if product.description != expected_description:
                product.description = expected_description
                changed_fields.append("description")
            if product.solve_text != "공문에서 해야 할 일을 바로 정리해요":
                product.solve_text = "공문에서 해야 할 일을 바로 정리해요"
                changed_fields.append("solve_text")
            if product.result_text != "실행용 업무 카드":
                product.result_text = "실행용 업무 카드"
                changed_fields.append("result_text")
            if changed_fields:
                product.save(update_fields=changed_fields)
                self.stdout.write(self.style.SUCCESS("[OK] Updated hwpxchat product essentials."))

        features = [
            {
                "icon": "📌",
                "title": "공문 업무 카드 정리",
                "description": "해야 할 일, 기한, 전달 대상을 한 번에 읽기 쉬운 카드로 정리합니다.",
            },
            {
                "icon": "💬",
                "title": "문서 근거 다시 묻기",
                "description": "정리된 뒤에도 문서 안 근거를 바탕으로 필요한 내용을 다시 물어볼 수 있습니다.",
            },
            {
                "icon": "⬇️",
                "title": "원문 복사와 다운로드",
                "description": "업무 카드 전체 복사와 원문 Markdown 다운로드로 바로 다른 작업에 이어 붙일 수 있습니다.",
            },
        ]
        feature_titles = {feature["title"] for feature in features}
        for feature in features:
            product_feature, created = ProductFeature.objects.get_or_create(
                product=product,
                title=feature["title"],
                defaults=feature,
            )
            if created:
                continue
            changed_fields = []
            if product_feature.icon != feature["icon"]:
                product_feature.icon = feature["icon"]
                changed_fields.append("icon")
            if product_feature.description != feature["description"]:
                product_feature.description = feature["description"]
                changed_fields.append("description")
            if changed_fields:
                product_feature.save(update_fields=changed_fields)
        ProductFeature.objects.filter(product=product).exclude(title__in=feature_titles).delete()

        manual, created = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": MANUAL_TITLE,
                "description": MANUAL_DESCRIPTION,
                "is_published": True,
            },
        )

        manual_update_fields = []
        if not created and manual.title in LEGACY_MANUAL_TITLES:
            manual.title = MANUAL_TITLE
            manual_update_fields.append("title")
        if not manual.description:
            manual.description = MANUAL_DESCRIPTION
            manual_update_fields.append("description")
        if not manual.is_published:
            manual.is_published = True
            manual_update_fields.append("is_published")
        if manual_update_fields:
            manual.save(update_fields=manual_update_fields)

        sections = [
            {
                "title": "시작하기",
                "content": "공문이나 한글 문서를 HWPX로 저장해 올리면 해야 할 일, 기한, 전달 대상을 업무 카드로 정리해 줍니다.",
                "layout_type": "text_only",
                "display_order": 1,
                "badge_text": "Step 1",
            },
            {
                "title": "카드 확인과 복사",
                "content": "정리된 카드에서 제목, 해야 할 일, 기한을 바로 다듬고 업무 카드 전체 복사로 다른 곳에 붙여 넣어 사용할 수 있습니다.",
                "layout_type": "text_only",
                "display_order": 2,
                "badge_text": "Step 2",
            },
            {
                "title": "원문과 다시 묻기",
                "content": "원문 Markdown을 내려받거나 문서에게 더 물어보기로 근거 문장을 다시 확인할 수 있습니다. HWP 파일은 업로드되지 않으니 HWPX로 변환해 주세요.",
                "layout_type": "text_only",
                "display_order": 3,
                "badge_text": "Tip",
            },
        ]
        section_titles = {section["title"] for section in sections}
        for section in sections:
            manual_section, created = ManualSection.objects.get_or_create(
                manual=manual,
                title=section["title"],
                defaults=section,
            )
            if created:
                continue
            changed_fields = []
            for field in ("content", "layout_type", "display_order", "badge_text"):
                if getattr(manual_section, field) != section[field]:
                    setattr(manual_section, field, section[field])
                    changed_fields.append(field)
            if changed_fields:
                manual_section.save(update_fields=changed_fields)
        manual.sections.exclude(title__in=section_titles).delete()

        self.stdout.write(self.style.SUCCESS("[OK] hwpxchat service ensured."))
