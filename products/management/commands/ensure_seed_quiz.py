from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure 씨앗 퀴즈 product exists in database"

    def handle(self, *args, **options):
        title = "씨앗 퀴즈"
        defaults = {
            "lead_text": "공식 퀴즈 은행과 CSV 업로드로 3문제 퀴즈를 빠르게 배포하고, 만점 학생에게 씨앗을 선물하세요.",
            "description": (
                "씨앗 퀴즈는 교사가 공식/공유 퀴즈 은행에서 문제를 선택해 배포하고, "
                "학생이 태블릿으로 5분 내에 풀이하는 교실 참여형 퀴즈 서비스입니다. "
                "만점 학생에게는 행복의 씨앗 보상이 자동으로 지급됩니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "📝",
            "color_theme": "purple",
            "card_size": "small",
            "display_order": 30,
            "service_type": "classroom",
            "external_url": "",
            "launch_route_name": "seed_quiz:landing",
        }
        mutable_fields = [
            "lead_text",
            "description",
            "price",
            "is_active",
            "is_featured",
            "is_guest_allowed",
            "icon",
            "color_theme",
            "card_size",
            "display_order",
            "service_type",
            "external_url",
            "launch_route_name",
        ]

        product, created = Product.objects.get_or_create(
            title=title,
            defaults=defaults,
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created product: {product.title}"))
        else:
            changed = []
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

        # 기능 목록
        feature_specs = [
            {
                "icon": "📚",
                "title": "퀴즈 은행 원클릭 적용",
                "legacy_titles": ["AI 퀴즈 자동 생성", "AI 퀴즈 생성"],
                "description": "학년/과목 필터로 공식 또는 공유 퀴즈를 골라 바로 우리 반에 배포할 수 있습니다.",
            },
            {
                "icon": "🗂️",
                "title": "CSV 업로드 지원",
                "legacy_titles": ["태블릿 최적화 UI", "학생 풀이 최적화"],
                "description": "교사가 보유한 문제를 CSV로 가져와 즉시 미리보기/배포할 수 있습니다.",
            },
            {
                "icon": "🌱",
                "title": "행복의 씨앗 연동",
                "legacy_titles": [],
                "description": "만점을 받은 학생에게 씨앗 보상이 자동으로 지급됩니다.",
            },
        ]

        used_feature_ids = set()
        for item in feature_specs:
            titles = [item["title"], *item.get("legacy_titles", [])]
            feature = ProductFeature.objects.filter(
                product=product, title__in=titles
            ).exclude(id__in=used_feature_ids).order_by("id").first()
            if feature is None:
                feature = (
                    ProductFeature.objects.filter(product=product)
                    .exclude(id__in=used_feature_ids)
                    .order_by("id")
                    .first()
                )
            if feature is None:
                feature = ProductFeature.objects.create(
                    product=product,
                    title=item["title"],
                    icon=item["icon"],
                    description=item["description"],
                )
                self.stdout.write(self.style.SUCCESS(f"  Added feature: {item['title']}"))
                used_feature_ids.add(feature.id)
                continue

            changed = []
            if feature.title != item["title"]:
                feature.title = item["title"]
                changed.append("title")
            if feature.icon != item["icon"]:
                feature.icon = item["icon"]
                changed.append("icon")
            if feature.description != item["description"]:
                feature.description = item["description"]
                changed.append("description")
            if changed:
                feature.save(update_fields=changed)
                self.stdout.write(self.style.SUCCESS(f"  Updated feature: {item['title']}"))
            used_feature_ids.add(feature.id)

        stale_features = ProductFeature.objects.filter(product=product).exclude(id__in=used_feature_ids)
        stale_feature_count = stale_features.count()
        if stale_feature_count:
            stale_features.delete()
            self.stdout.write(self.style.SUCCESS(f"  Removed stale features: {stale_feature_count}"))

        # 서비스 매뉴얼
        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": "씨앗 퀴즈 시작 가이드",
                "description": "퀴즈 선택부터 배포, 학생 풀이, 씨앗 보상까지 전체 흐름을 안내합니다.",
                "is_published": True,
            },
        )

        manual_changed = []
        target_title = "씨앗 퀴즈 시작 가이드"
        if manual.title != target_title:
            manual.title = target_title
            manual_changed.append("title")
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        target_desc = "퀴즈 선택부터 배포, 학생 풀이, 씨앗 보상까지 전체 흐름을 안내합니다."
        if manual.description != target_desc:
            manual.description = target_desc
            manual_changed.append("description")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        section_specs = [
            {
                "title": "시작하기",
                "legacy_titles": [],
                "content": (
                    "1) 교실 상세 화면에서 '씨앗 퀴즈' 버튼 클릭 → 2) 범위/과목/학년 필터로 퀴즈 은행 조회 "
                    "→ 3) 미리보기 확인 후 '배포하기' → 4) 학생에게 접속 주소 공유 순서로 진행합니다."
                ),
                "display_order": 1,
            },
            {
                "title": "퀴즈 선택법",
                "legacy_titles": ["퀴즈 생성법"],
                "content": (
                    "과목(상식/수학/국어/과학/사회/영어)과 학년(1~6)을 선택해 공식 또는 공유 퀴즈를 조회하세요. "
                    "원하는 세트를 선택하면 미리보기 화면으로 이동하며, 배포 전 정답/해설을 확인할 수 있습니다."
                ),
                "display_order": 2,
            },
            {
                "title": "학생 안내",
                "legacy_titles": [],
                "content": (
                    "학생은 공유받은 주소(seed-quiz/gate/반코드/)에 접속하여 번호와 이름을 입력하면 시작됩니다. "
                    "3문항을 순서대로 풀고, 마지막 문항 제출 즉시 채점과 보상이 이루어집니다. "
                    "만점+보호자 동의 완료 학생에게 씨앗 2개가 자동 지급됩니다."
                ),
                "display_order": 3,
            },
            {
                "title": "진행 현황 확인",
                "legacy_titles": [],
                "content": (
                    "교사 대시보드 하단의 '진행 현황'에서 접속/제출/만점 학생 수를 실시간으로 확인할 수 있습니다. "
                    "현황은 15초마다 자동으로 갱신됩니다."
                ),
                "display_order": 4,
            },
            {
                "title": "보상 정책",
                "legacy_titles": [],
                "content": (
                    "보상 조건: 3문항 모두 정답(만점) + 보호자 동의 완료(approved 상태). "
                    "보상 씨앗 수: 2개. 중복 제출 방지: 동일 학생이 같은 퀴즈에 보상은 1회만 지급됩니다."
                ),
                "display_order": 5,
            },
        ]

        used_section_ids = set()
        for item in section_specs:
            titles = [item["title"], *item.get("legacy_titles", [])]
            section = (
                ManualSection.objects.filter(manual=manual, title__in=titles)
                .exclude(id__in=used_section_ids)
                .order_by("display_order", "id")
                .first()
            )
            if section is None:
                section = (
                    ManualSection.objects.filter(manual=manual, display_order=item["display_order"])
                    .exclude(id__in=used_section_ids)
                    .order_by("id")
                    .first()
                )
            if section is None:
                section = (
                    ManualSection.objects.filter(manual=manual)
                    .exclude(id__in=used_section_ids)
                    .order_by("display_order", "id")
                    .first()
                )

            if section is None:
                section = ManualSection.objects.create(
                    manual=manual,
                    title=item["title"],
                    content=item["content"],
                    display_order=item["display_order"],
                )
            else:
                changed = []
                if section.title != item["title"]:
                    section.title = item["title"]
                    changed.append("title")
                if section.content != item["content"]:
                    section.content = item["content"]
                    changed.append("content")
                if section.display_order != item["display_order"]:
                    section.display_order = item["display_order"]
                    changed.append("display_order")
                if changed:
                    section.save(update_fields=changed)
            used_section_ids.add(section.id)

        stale_sections = ManualSection.objects.filter(manual=manual).exclude(id__in=used_section_ids)
        stale_section_count = stale_sections.count()
        if stale_section_count:
            stale_sections.delete()
            self.stdout.write(self.style.SUCCESS(f"  Removed stale manual sections: {stale_section_count}"))

        self.stdout.write(self.style.SUCCESS("ensure_seed_quiz completed"))
