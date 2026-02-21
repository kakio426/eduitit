from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure HWPX chat product and manual exist in database"

    def handle(self, *args, **options):
        title = "HWPX 문서 AI 대화"

        product, created = Product.objects.get_or_create(
            title=title,
            defaults={
                "lead_text": "HWPX 내부 XML을 직접 파싱해 문서 기반 AI 대화를 시작하세요.",
                "description": (
                    "교사가 업로드한 HWPX 파일을 서버 메모리에서 직접 파싱하여 Markdown으로 변환하고, "
                    "그 문서 내용을 기반으로 AI(Gemini/Claude)와 질의응답할 수 있는 서비스입니다."
                ),
                "price": 0.00,
                "is_active": True,
                "is_featured": False,
                "is_guest_allowed": False,
                "icon": "📄",
                "color_theme": "green",
                "card_size": "small",
                "display_order": 24,
                "service_type": "work",
                "external_url": "",
                "launch_route_name": "hwpxchat:main",
                "solve_text": "한글 문서 내용을 AI가 정확히 읽게 해주세요",
                "result_text": "문서 근거 기반 답변",
                "time_text": "1분",
            },
        )

        if not created and not product.is_active:
            product.is_active = True
            product.save(update_fields=["is_active"])

        features = [
            {
                "icon": "🧩",
                "title": "HWPX 직접 파싱",
                "description": "zipfile + XML 파싱으로 Contents/section*.xml을 직접 읽습니다.",
            },
            {
                "icon": "📊",
                "title": "표 자동 Markdown 변환",
                "description": "표(Table)를 LLM이 잘 읽는 Markdown 표 형태로 변환합니다.",
            },
            {
                "icon": "🤖",
                "title": "문서 기반 AI 대화",
                "description": "Gemini/Claude로 문서 근거 중심 질의응답을 제공합니다.",
            },
        ]
        for feature in features:
            ProductFeature.objects.get_or_create(
                product=product,
                title=feature["title"],
                defaults=feature,
            )

        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": "HWPX 문서 AI 대화 사용 가이드",
                "description": "HWPX 업로드부터 문서 기반 AI 질의응답까지 빠르게 시작하는 방법입니다.",
                "is_published": True,
            },
        )

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
                    "title": "문서 기반 답변 활용",
                    "content": "문서에 없는 내용은 추측하지 않도록 설계되어 있으므로, 필요한 정보가 없으면 문서를 보완해 다시 질문해 주세요.",
                    "layout_type": "text_only",
                    "display_order": 3,
                    "badge_text": "Tip",
                },
            ]
            for section in sections:
                ManualSection.objects.create(manual=manual, **section)

        self.stdout.write(self.style.SUCCESS("[OK] HWPX chat service ensured."))

