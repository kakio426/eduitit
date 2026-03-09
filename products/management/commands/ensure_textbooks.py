from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure textbooks product and manual exist in database"

    PRODUCT_TITLE = "교과서 라이브 수업"
    LAUNCH_ROUTE = "textbooks:main"

    def handle(self, *args, **options):
        defaults = {
            "lead_text": "교과서 PDF를 올리고, 교사 화면·TV 화면·학생 화면을 같은 세션으로 연결합니다.",
            "description": (
                "교과서 라이브 수업은 PDF 교과서를 올린 뒤 교사 화면에서 페이지를 넘기고, TV 발표 화면과 학생 기기를 같은 페이지로 동기화하는 수업 전용 서비스입니다. "
                "학생은 입장 코드로 접속하고, 교사는 페이지 이동과 기본 필기를 한 흐름으로 제어할 수 있습니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": True,
            "is_guest_allowed": True,
            "icon": "📘",
            "color_theme": "blue",
            "card_size": "small",
            "display_order": 15,
            "service_type": "classroom",
            "external_url": "",
            "launch_route_name": self.LAUNCH_ROUTE,
            "solve_text": "PDF 교과서를 학생과 같이 보며 수업하고 싶어요",
            "result_text": "교사·TV·학생 동기화 수업 화면",
            "time_text": "3분",
        }

        product = Product.objects.filter(launch_route_name=self.LAUNCH_ROUTE).order_by("id").first()
        if not product:
            product = Product.objects.filter(title=self.PRODUCT_TITLE).order_by("id").first()

        if product is None:
            product = Product.objects.create(title=self.PRODUCT_TITLE, **defaults)
            self.stdout.write(self.style.SUCCESS(f"Created product: {product.title}"))
        else:
            changed_fields = []
            for field_name, value in defaults.items():
                if getattr(product, field_name) != value:
                    setattr(product, field_name, value)
                    changed_fields.append(field_name)
            if product.title != self.PRODUCT_TITLE:
                product.title = self.PRODUCT_TITLE
                changed_fields.append("title")
            if changed_fields:
                product.save(update_fields=list(dict.fromkeys(changed_fields)))
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Updated product essentials: {', '.join(dict.fromkeys(changed_fields))}"
                    )
                )
            else:
                self.stdout.write(self.style.SUCCESS(f"Product already exists: {product.title}"))

        feature_specs = [
            {
                "icon": "📄",
                "title": "PDF 업로드",
                "description": "비밀번호 없는 교과서 PDF를 올리면 페이지 수를 읽고 수업 자료로 바로 저장합니다.",
            },
            {
                "icon": "🖥️",
                "title": "교사·TV·학생 동기화",
                "description": "교사 화면에서 넘긴 페이지를 TV 발표 화면과 학생 기기에 같은 흐름으로 맞춰 보여줍니다.",
            },
            {
                "icon": "✏️",
                "title": "라이브 필기",
                "description": "수업 중 페이지 위에 기본 필기를 올리고 학생 화면과 함께 맞춰 볼 수 있습니다.",
            },
        ]
        for item in feature_specs:
            ProductFeature.objects.update_or_create(
                product=product,
                title=item["title"],
                defaults={
                    "icon": item["icon"],
                    "description": item["description"],
                },
            )

        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": "교과서 라이브 수업 사용 가이드",
                "description": "PDF 업로드부터 라이브 수업 시작, 학생 참여까지의 흐름을 안내합니다.",
                "is_published": True,
            },
        )
        manual_changed = []
        if manual.title != "교과서 라이브 수업 사용 가이드":
            manual.title = "교과서 라이브 수업 사용 가이드"
            manual_changed.append("title")
        if manual.description != "PDF 업로드부터 라이브 수업 시작, 학생 참여까지의 흐름을 안내합니다.":
            manual.description = "PDF 업로드부터 라이브 수업 시작, 학생 참여까지의 흐름을 안내합니다."
            manual_changed.append("description")
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        section_specs = [
            ("PDF 올리기", "과목과 단원명을 입력한 뒤 PDF 파일을 올리면 교과서 자료가 저장됩니다.", 1),
            ("라이브 수업 시작", "상세 화면에서 라이브 수업을 시작하면 입장 코드와 학생 접속 QR이 함께 생성됩니다.", 2),
            ("학생 참여", "학생은 입장 코드로 접속하고, 교사는 교사 화면과 TV 화면을 분리해 수업을 진행할 수 있습니다.", 3),
        ]
        for title, content, display_order in section_specs:
            ManualSection.objects.update_or_create(
                manual=manual,
                title=title,
                defaults={
                    "content": content,
                    "display_order": display_order,
                },
            )

        self.stdout.write(self.style.SUCCESS("ensure_textbooks completed"))
