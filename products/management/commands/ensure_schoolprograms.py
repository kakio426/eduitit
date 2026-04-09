from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure 학교 체험·행사 찾기 product exists in database"

    def handle(self, *args, **options):
        title = "학교 체험·행사 찾기"
        defaults = {
            "lead_text": "학교로 찾아오는 체험학습, 연수, 행사를 시도·세부 지역·주제로 바로 비교하세요.",
            "description": (
                "학교 체험·행사 찾기는 교사와 교육행사업체를 연결하는 공개 검색형 서비스입니다. "
                "교사는 시도와 세부 지역, 주제로 프로그램을 찾고 문의를 남길 수 있고, 업체는 소개 페이지와 프로그램 등록글을 통해 "
                "학교 현장에 맞는 제안을 보낼 수 있습니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": True,
            "icon": "🎪",
            "color_theme": "orange",
            "card_size": "small",
            "display_order": 33,
            "service_type": "classroom",
            "external_url": "",
            "launch_route_name": "schoolprograms:landing",
            "solve_text": "학교에 맞는 외부 프로그램을 한곳에서 찾고 싶어요",
            "result_text": "비교 가능한 프로그램 목록과 문의 스레드",
            "time_text": "3분",
        }
        mutable_fields = [
            "lead_text",
            "description",
            "price",
            "is_guest_allowed",
            "icon",
            "color_theme",
            "card_size",
            "display_order",
            "service_type",
            "external_url",
            "launch_route_name",
            "solve_text",
            "result_text",
            "time_text",
        ]

        product = Product.objects.filter(launch_route_name="schoolprograms:landing").order_by("id").first()
        created = False
        if product is None:
            product = Product.objects.filter(title__in=[title, "학교 프로그램 찾기"]).order_by("id").first()
        if product is None:
            product = Product.objects.create(title=title, **defaults)
            created = True
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created product: {product.title}"))
        else:
            changed = []
            if product.title != title:
                product.title = title
                changed.append("title")
            for field in mutable_fields:
                new_value = defaults[field]
                if getattr(product, field) != new_value:
                    setattr(product, field, new_value)
                    changed.append(field)
            if changed:
                product.save(update_fields=changed)
                self.stdout.write(self.style.SUCCESS(f"Updated product fields: {', '.join(changed)}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"Product already exists: {product.title}"))

        feature_specs = [
            {
                "icon": "🗺️",
                "title": "지역·주제 검색",
                "description": "시도와 세부 지역, 카테고리, 대상, 주제로 프로그램을 빠르게 좁혀 찾을 수 있습니다.",
            },
            {
                "icon": "💬",
                "title": "문의 스레드",
                "description": "전화 없이도 요청 조건을 남기고 업체 답변을 같은 스레드에서 이어서 확인합니다.",
            },
            {
                "icon": "📄",
                "title": "가벼운 제안 카드",
                "description": "업체가 비용 범위, 포함 항목, 일정 메모를 부담 없이 제안 카드로 보낼 수 있습니다.",
            },
        ]
        for item in feature_specs:
            feature, feature_created = ProductFeature.objects.get_or_create(
                product=product,
                title=item["title"],
                defaults={"icon": item["icon"], "description": item["description"]},
            )
            if feature_created:
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
                "title": "학교 체험·행사 찾기 시작 가이드",
                "description": "교사용 검색부터 업체 등록, 문의·제안 흐름까지 바로 따라갈 수 있습니다.",
                "is_published": True,
            },
        )
        manual_changed = []
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        manual_title = "학교 체험·행사 찾기 시작 가이드"
        if manual.title != manual_title:
            manual.title = manual_title
            manual_changed.append("title")
        manual_description = "교사용 검색부터 업체 등록, 문의·제안 흐름까지 바로 따라갈 수 있습니다."
        if manual.description != manual_description:
            manual.description = manual_description
            manual_changed.append("description")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        section_specs = [
            (
                "교사용 검색",
                "1) 시도와 세부 지역, 카테고리, 대상으로 프로그램을 찾고 2) 상세 페이지에서 조건을 남겨 문의를 시작합니다.",
                1,
            ),
            (
                "업체 등록",
                "업체 정보와 증빙 서류를 먼저 입력한 뒤 대표 프로그램을 등록하고 심사 요청을 보냅니다.",
                2,
            ),
            (
                "문의·제안 흐름",
                "교사가 문의를 보내면 업체가 스레드로 답변하고, 필요하면 비용 범위와 일정 메모를 제안 카드로 보냅니다.",
                3,
            ),
            (
                "승인 정책",
                "프로그램 등록글은 운영 승인 후에만 공개 검색 결과에 노출됩니다.",
                4,
            ),
        ]
        for title_text, content, order in section_specs:
            section, section_created = ManualSection.objects.get_or_create(
                manual=manual,
                title=title_text,
                defaults={"content": content, "display_order": order},
            )
            if section_created:
                continue
            changed = []
            if section.content != content:
                section.content = content
                changed.append("content")
            if section.display_order != order:
                section.display_order = order
                changed.append("display_order")
            if changed:
                section.save(update_fields=changed)

        self.stdout.write(self.style.SUCCESS("ensure_schoolprograms completed"))
