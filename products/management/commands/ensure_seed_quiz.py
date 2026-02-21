from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure 씨앗 퀴즈 product exists in database"

    def handle(self, *args, **options):
        title = "씨앗 퀴즈"
        defaults = {
            "lead_text": "AI가 만든 3문제 퀴즈로 수업 집중도를 높이고, 만점 학생에게 씨앗을 선물하세요.",
            "description": (
                "씨앗 퀴즈는 교사가 원클릭으로 AI 퀴즈를 생성하고, "
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
            "is_guest_allowed",
            "icon",
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
                "icon": "🤖",
                "title": "AI 퀴즈 자동 생성",
                "legacy_titles": [],
                "description": "과목과 학년을 선택하면 DeepSeek AI가 3문항 퀴즈를 즉시 생성합니다.",
            },
            {
                "icon": "📱",
                "title": "태블릿 최적화 UI",
                "legacy_titles": [],
                "description": "학생이 태블릿으로 손쉽게 풀 수 있는 큰 버튼과 간결한 화면으로 구성되어 있습니다.",
            },
            {
                "icon": "🌱",
                "title": "행복의 씨앗 연동",
                "legacy_titles": [],
                "description": "만점을 받은 학생에게 씨앗 보상이 자동으로 지급됩니다.",
            },
        ]

        for item in feature_specs:
            titles = [item["title"], *item.get("legacy_titles", [])]
            feature = ProductFeature.objects.filter(
                product=product, title__in=titles
            ).order_by("id").first()
            if feature is None:
                ProductFeature.objects.create(
                    product=product,
                    title=item["title"],
                    icon=item["icon"],
                    description=item["description"],
                )
                self.stdout.write(self.style.SUCCESS(f"  Added feature: {item['title']}"))
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

        # 서비스 매뉴얼
        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": "씨앗 퀴즈 시작 가이드",
                "description": "퀴즈 생성부터 배포, 학생 풀이, 씨앗 보상까지 전체 흐름을 안내합니다.",
                "is_published": True,
            },
        )

        manual_changed = []
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        target_desc = "퀴즈 생성부터 배포, 학생 풀이, 씨앗 보상까지 전체 흐름을 안내합니다."
        if manual.description != target_desc:
            manual.description = target_desc
            manual_changed.append("description")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        sections = [
            (
                "시작하기",
                (
                    "1) 교실 상세 화면에서 '씨앗 퀴즈' 버튼 클릭 → 2) 과목과 학년 선택 후 'AI 퀴즈 생성' 클릭 "
                    "→ 3) 미리보기 확인 후 '배포하기' → 4) 학생에게 접속 주소 공유 순서로 진행합니다."
                ),
                1,
            ),
            (
                "퀴즈 생성법",
                (
                    "과목(상식/수학/국어/과학/사회/영어)과 학년(1~6)을 선택하고 'AI 퀴즈 생성'을 누르세요. "
                    "AI 생성에 실패할 경우 자동으로 기본 문제 은행으로 전환됩니다. "
                    "마음에 들지 않으면 '다시 생성' 버튼으로 새 문제를 받을 수 있습니다."
                ),
                2,
            ),
            (
                "학생 안내",
                (
                    "학생은 공유받은 주소(seed-quiz/gate/반코드/)에 접속하여 번호와 이름을 입력하면 시작됩니다. "
                    "3문항을 순서대로 풀고, 마지막 문항 제출 즉시 채점과 보상이 이루어집니다. "
                    "만점+보호자 동의 완료 학생에게 씨앗 2개가 자동 지급됩니다."
                ),
                3,
            ),
            (
                "진행 현황 확인",
                (
                    "교사 대시보드 하단의 '진행 현황'에서 접속/제출/만점 학생 수를 실시간으로 확인할 수 있습니다. "
                    "현황은 15초마다 자동으로 갱신됩니다."
                ),
                4,
            ),
            (
                "보상 정책",
                (
                    "보상 조건: 3문항 모두 정답(만점) + 보호자 동의 완료(approved 상태). "
                    "보상 씨앗 수: 2개. 중복 제출 방지: 동일 학생이 같은 퀴즈에 보상은 1회만 지급됩니다."
                ),
                5,
            ),
        ]

        for section_title, content, order in sections:
            section, section_created = ManualSection.objects.get_or_create(
                manual=manual,
                title=section_title,
                defaults={"content": content, "display_order": order},
            )
            if not section_created:
                changed = []
                if section.display_order != order:
                    section.display_order = order
                    changed.append("display_order")
                if section.content != content:
                    section.content = content
                    changed.append("content")
                if changed:
                    section.save(update_fields=changed)

        self.stdout.write(self.style.SUCCESS("ensure_seed_quiz completed"))
