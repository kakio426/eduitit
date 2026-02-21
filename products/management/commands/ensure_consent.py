from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


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

        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": "동의서는 나에게 맡겨 사용 가이드",
                "description": "문서 업로드부터 제출 결과 다운로드까지 실사용 흐름을 안내합니다.",
                "is_published": True,
            },
        )

        manual_changed = []
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        if manual.description != "문서 업로드부터 제출 결과 다운로드까지 실사용 흐름을 안내합니다.":
            manual.description = "문서 업로드부터 제출 결과 다운로드까지 실사용 흐름을 안내합니다."
            manual_changed.append("description")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        sections = [
            (
                "시작하기",
                "안내문을 업로드한 뒤 수신자(학생/보호자)를 등록하고 제출 링크를 발송하세요.",
                1,
            ),
            (
                "진행 상태 확인",
                "대시보드에서 제출/미제출 상태를 확인하고, 미제출 대상에게 링크를 다시 안내하세요.",
                2,
            ),
            (
                "결과 보관",
                "제출 결과를 CSV/PDF로 내려받아 학급 문서 보관 규정에 맞게 정리하세요.",
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
                section_changed = []
                if section.content != content:
                    section.content = content
                    section_changed.append("content")
                if section.display_order != order:
                    section.display_order = order
                    section_changed.append("display_order")
                if section_changed:
                    section.save(update_fields=section_changed)

        if created:
            self.stdout.write(self.style.SUCCESS(f"[OK] Created Consent product (ID: {product.id})"))
        else:
            self.stdout.write(self.style.SUCCESS(f"[OK] Ensured Consent product (ID: {product.id})"))
