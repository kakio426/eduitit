from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure Docsign product exists in database"

    def handle(self, *args, **options):
        defaults = {
            "lead_text": "PDF를 올리고 내가 바로 사인한 뒤 내려받습니다.",
            "description": "내 문서를 올린 뒤 사인 위치를 잡고, 직접 서명한 PDF를 바로 다운로드합니다.",
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "fa-solid fa-file-signature",
            "color_theme": "blue",
            "card_size": "small",
            "display_order": 22,
            "service_type": "collect_sign",
            "external_url": "",
            "launch_route_name": "docsign:list",
            "solve_text": "내 문서에 바로 사인",
            "result_text": "사인된 PDF",
            "time_text": "3분",
        }
        product = Product.objects.filter(launch_route_name="docsign:list").order_by("id").first()
        created = product is None
        if product is None:
            product = Product.objects.create(title="잇티PDF사인", **defaults)
        else:
            changed_fields = []
            if product.title != "잇티PDF사인":
                product.title = "잇티PDF사인"
                changed_fields.append("title")
            for field_name, expected in defaults.items():
                if getattr(product, field_name) != expected:
                    setattr(product, field_name, expected)
                    changed_fields.append(field_name)
            if changed_fields:
                product.save(update_fields=changed_fields)
        Product.objects.filter(title="인쇄 NONO 온라인 사인").exclude(id=product.id).delete()

        updates = {
            "external_url": "",
            "launch_route_name": "docsign:list",
            "service_type": "collect_sign",
            "icon": "fa-solid fa-file-signature",
            "color_theme": "blue",
        }
        changed_fields = []
        for field_name, expected in updates.items():
            if getattr(product, field_name) != expected:
                setattr(product, field_name, expected)
                changed_fields.append(field_name)
        if changed_fields:
            product.save(update_fields=changed_fields)

        features = [
            ("fa-solid fa-file-arrow-up", "PDF 업로드", "내 문서를 바로 올립니다."),
            ("fa-solid fa-up-down-left-right", "사인 위치 지정", "문서 위에서 위치와 크기를 맞춥니다."),
            ("fa-solid fa-download", "사인된 PDF 다운로드", "완성된 PDF를 바로 받습니다."),
        ]
        for icon, title, description in features:
            ProductFeature.objects.get_or_create(
                product=product,
                title=title,
                defaults={"icon": icon, "description": description},
            )

        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": "잇티PDF사인 사용 가이드",
                "description": "PDF 업로드부터 다운로드까지 바로 이어갑니다.",
                "is_published": True,
            },
        )
        manual_updates = []
        if manual.title != "잇티PDF사인 사용 가이드":
            manual.title = "잇티PDF사인 사용 가이드"
            manual_updates.append("title")
        if manual.description != "PDF 업로드부터 다운로드까지 바로 이어갑니다.":
            manual.description = "PDF 업로드부터 다운로드까지 바로 이어갑니다."
            manual_updates.append("description")
        if not manual.is_published:
            manual.is_published = True
            manual_updates.append("is_published")
        if manual_updates:
            manual.save(update_fields=manual_updates)

        sections = [
            ("PDF 올리기", "사인할 PDF를 올립니다.", 1),
            ("위치 잡기", "문서 위에서 사인 위치를 맞춥니다.", 2),
            ("사인 받기", "직접 사인하고 PDF를 내려받습니다.", 3),
        ]
        for title, content, order in sections:
            section, section_created = ManualSection.objects.get_or_create(
                manual=manual,
                title=title,
                defaults={"content": content, "display_order": order},
            )
            if not section_created:
                update_fields = []
                if section.content != content:
                    section.content = content
                    update_fields.append("content")
                if section.display_order != order:
                    section.display_order = order
                    update_fields.append("display_order")
                if update_fields:
                    section.save(update_fields=update_fields)

        label = "Created" if created else "Ensured"
        self.stdout.write(self.style.SUCCESS(f"[OK] {label} Docsign product (ID: {product.id})"))
