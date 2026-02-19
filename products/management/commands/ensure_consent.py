from django.core.management.base import BaseCommand

from products.models import Product, ProductFeature


class Command(BaseCommand):
    help = "Ensure Consent product exists in database"

    def handle(self, *args, **options):
        product, created = Product.objects.get_or_create(
            title="동의서는 나에게 맡겨",
            defaults={
                "lead_text": "문서 올리고, 수신자 등록하고, 링크 보내면 동의서 수합이 완료됩니다.",
                "description": "안내문 업로드, 수신자 등록, 링크 발송, 제출 결과 다운로드를 한 번에 처리합니다.",
                "price": 0.00,
                "is_active": True,
                "is_featured": False,
                "is_guest_allowed": False,
                "icon": "fa-solid fa-file-signature",
                "color_theme": "purple",
                "card_size": "small",
                "display_order": 21,
                "service_type": "classroom",
                "external_url": "",
                "solve_text": "학부모 동의서 회수/보관의 번거로움",
                "result_text": "학부모 제출 링크 + 결과 CSV/PDF",
                "time_text": "3분",
            },
        )

        updates = {
            "is_active": True,
            "external_url": "",
            "service_type": "classroom",
        }
        changed = False
        for key, value in updates.items():
            if getattr(product, key) != value:
                setattr(product, key, value)
                changed = True
        if changed:
            product.save()

        features = [
            ("fa-solid fa-mobile-screen-button", "학부모 동의 링크(확인→서명→완료)", "본인확인 → 동의/비동의 + 손서명 → 완료"),
            ("fa-solid fa-table-list", "교사용 진행상태 대시보드", "수신자 상태와 링크, 다운로드를 한 화면에서 관리"),
            ("fa-solid fa-file-pdf", "제출 결과 PDF 생성", "학생별 제출 결과를 묶어 PDF로 다운로드"),
        ]
        for icon, title, desc in features:
            ProductFeature.objects.get_or_create(
                product=product,
                title=title,
                defaults={"icon": icon, "description": desc},
            )

        # Legacy wording normalize
        ProductFeature.objects.filter(
            product=product,
            title="학부모 3단계 위저드",
        ).update(
            title="학부모 동의 링크(확인→서명→완료)",
            description="본인확인 → 동의/비동의 + 손서명 → 완료",
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f"[OK] Created Consent product (ID: {product.id})"))
        else:
            self.stdout.write(self.style.SUCCESS(f"[OK] Ensured Consent product (ID: {product.id})"))
