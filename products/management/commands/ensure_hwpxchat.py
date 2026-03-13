from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


SERVICE_TITLE = "한글문서 AI야 읽어줘"
LEGACY_TITLES = ("한글 문서 톡톡", "HWPX 문서 AI 대화")

MANUAL_TITLE = "한글문서 AI야 읽어줘 사용 가이드"
LEGACY_MANUAL_TITLES = (
    "한글 문서 톡톡 사용 가이드",
    "HWPX 문서 AI 대화 사용 가이드",
)
MANUAL_DESCRIPTION = "한글(HWPX) 파일 업로드부터 문서 기반 대화까지 빠르게 시작하는 방법입니다."


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
                lead_text="한글 문서를 올리면 AI가 문서 내용을 읽고 답해줘요.",
                description=(
                    "교사가 업로드한 HWPX 파일을 서버 메모리에서 직접 파싱해 Markdown으로 변환하고, "
                    "문서 내용을 바탕으로 AI(Gemini/Claude)와 질의응답할 수 있는 서비스입니다."
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
                solve_text="한글 문서 내용을 빠르게 정리하고 질문하고 싶어요",
                result_text="문서 근거 기반 답변",
                time_text="1분",
            )
            self.stdout.write(self.style.SUCCESS("[OK] Created hwpxchat service product."))
        else:
            changed_fields = []
            if not product.launch_route_name:
                product.launch_route_name = "hwpxchat:main"
                changed_fields.append("launch_route_name")
            if changed_fields:
                product.save(update_fields=changed_fields)
                self.stdout.write(self.style.SUCCESS("[OK] Updated hwpxchat product essentials."))

        features = [
            {
                "icon": "🧩",
                "title": "문서 그대로 읽기",
                "description": "HWPX 내부 XML을 직접 읽어 문서 내용을 놓치지 않습니다.",
            },
            {
                "icon": "🧠",
                "title": "표도 깔끔하게 이해",
                "description": "표를 Markdown 형식으로 변환해 AI가 구조를 잘 이해하게 만듭니다.",
            },
            {
                "icon": "💬",
                "title": "질문하면 바로 답변",
                "description": "문서 근거 중심으로 Gemini/Claude가 답변을 제공합니다.",
            },
        ]
        for feature in features:
            ProductFeature.objects.get_or_create(
                product=product,
                title=feature["title"],
                defaults=feature,
            )

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

        if manual.sections.count() == 0:
            sections = [
                {
                    "title": "시작하기",
                    "content": "서비스에서 HWPX 파일을 업로드하고 질문을 입력하면 문서 기반 답변을 받을 수 있습니다.",
                    "layout_type": "text_only",
                    "display_order": 1,
                    "badge_text": "Step 1",
                },
                {
                    "title": "파일 형식 주의",
                    "content": "HWP 파일은 업로드되지 않습니다. 한글에서 '다른 이름으로 저장 → HWPX'로 변환해 주세요.",
                    "layout_type": "text_only",
                    "display_order": 2,
                    "badge_text": "Step 2",
                },
                {
                    "title": "답변 정확도 높이기",
                    "content": "문서에 없는 내용은 추측하지 않도록 설계되어 있으니, 필요한 정보가 없으면 문서를 보완해 다시 질문해 주세요.",
                    "layout_type": "text_only",
                    "display_order": 3,
                    "badge_text": "Tip",
                },
            ]
            for section in sections:
                ManualSection.objects.create(manual=manual, **section)

        self.stdout.write(self.style.SUCCESS("[OK] hwpxchat service ensured."))
