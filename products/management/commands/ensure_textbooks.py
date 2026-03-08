from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure textbooks product and manual exist in database"

    def handle(self, *args, **options):
        defaults = {
            "lead_text": "PDF 교과서를 올리고 실시간으로 같은 화면을 함께 보는 수업 도구입니다.",
            "description": (
                "교사가 PDF 교과서를 업로드하면 TV 발표 화면과 학생 태블릿 화면을 같은 페이지로 맞추고, "
                "펜과 도형 필기를 실시간으로 동기화하는 라이브 수업 도구입니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "📘",
            "color_theme": "blue",
            "card_size": "small",
            "display_order": 26,
            "service_type": "classroom",
            "external_url": "",
            "launch_route_name": "textbooks:main",
            "solve_text": "교과서 PDF를 같은 화면으로 수업하고 싶어요",
            "result_text": "라이브 수업 화면 + 학생 동기화",
            "time_text": "2분",
        }
        product, created = Product.objects.get_or_create(title="교과서 라이브 수업", defaults=defaults)
        if not created:
            changed = []
            for field, value in defaults.items():
                current = getattr(product, field)
                if field in {"is_active", "launch_route_name", "service_type"} and current != value:
                    setattr(product, field, value)
                    changed.append(field)
            if changed:
                product.save(update_fields=changed)
                self.stdout.write(self.style.SUCCESS(f"[ensure_textbooks] updated: {', '.join(changed)}"))

        features = [
            {"icon": "🖥️", "title": "TV 발표 화면", "description": "교사용 조작 화면과 발표용 전체화면을 분리해 수업 흐름을 유지합니다."},
            {"icon": "📲", "title": "학생 동기화", "description": "QR과 6자리 입장코드로 학생 태블릿을 같은 페이지에 바로 연결합니다."},
            {"icon": "✍️", "title": "기본 필기", "description": "펜, 형광펜, 네모, 동그라미, 레이저 포인터를 같은 화면에 동기화합니다."},
        ]
        for feature in features:
            ProductFeature.objects.get_or_create(product=product, title=feature["title"], defaults=feature)

        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": "교과서 라이브 수업 사용 가이드",
                "description": "PDF 업로드부터 학생 접속, 라이브 필기까지 빠르게 익히는 안내입니다.",
                "is_published": True,
            },
        )
        changed = []
        if not manual.is_published:
            manual.is_published = True
            changed.append("is_published")
        if not (manual.description or "").strip():
            manual.description = "PDF 업로드부터 학생 접속, 라이브 필기까지 빠르게 익히는 안내입니다."
            changed.append("description")
        if changed:
            manual.save(update_fields=changed)

        sections = [
            ("시작하기", "PDF 자료를 만들고 라이브 수업 시작 버튼으로 세션을 열면 학생용 입장코드와 QR이 생성됩니다.", 1),
            ("수업 진행", "교사는 페이지 이동, 펜, 형광펜, 도형, 레이저 포인터를 사용하고 학생은 같은 화면을 따라옵니다.", 2),
            ("활용 팁", "TV는 발표용 화면으로, 노트북은 교사용 조작 화면으로 분리하면 수업 흐름이 가장 안정적입니다.", 3),
        ]
        for title, content, display_order in sections:
            ManualSection.objects.get_or_create(
                manual=manual,
                title=title,
                defaults={"content": content, "display_order": display_order},
            )

        self.stdout.write(self.style.SUCCESS("[ensure_textbooks] Done"))
