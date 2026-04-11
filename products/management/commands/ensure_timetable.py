from django.core.management.base import BaseCommand
from django.db.models import Q

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure timetable product exists in database"

    def handle(self, *args, **options):
        title = "우리학교 시간표"
        legacy_titles = [
            "학교 시간표 편집 허브",
            "전담 시간표·특별실 배치 도우미",
        ]
        defaults = {
            "lead_text": "새 학기를 만들고, 반별로 입력받고, 검토와 확정까지 한 화면에서 운영하는 우리학교 시간표입니다.",
            "description": (
                "학년별 시간표를 직접 정리하고, 교사 겹침, 강사 더블부킹, 특별실 수용량 초과, 학교 전체·학년 공통 행사를 바로 확인한 뒤 "
                "반별 입력 링크 배포, 날짜별 예외 일정 입력, 검토 상태 확인, 스냅샷 복원, 읽기 전용 인쇄/PDF 저장까지 이어서 처리할 수 있는 우리학교 시간표 서비스입니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": True,
            "icon": "🗓️",
            "color_theme": "blue",
            "card_size": "small",
            "display_order": 35,
            "service_type": "work",
            "external_url": "",
            "launch_route_name": "timetable:main",
        }
        mutable_fields = [
            "lead_text",
            "description",
            "price",
            "is_guest_allowed",
            "icon",
            "service_type",
            "external_url",
            "launch_route_name",
        ]

        product = (
            Product.objects.filter(
                Q(launch_route_name="timetable:main") | Q(title=title) | Q(title__in=legacy_titles)
            )
            .order_by("id")
            .first()
        )
        created = False
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
                "icon": "🧭",
                "title": "시간표 직접 편집",
                "description": "학년 전체 시간표를 한 화면에서 배정하고 바로 저장할 수 있습니다.",
            },
            {
                "icon": "🚨",
                "title": "실시간 겹침 감지",
                "description": "교사 겹침과 특별실 수용량 초과를 즉시 점검합니다.",
            },
            {
                "icon": "🎉",
                "title": "학교·학년 공통 행사",
                "description": "학교 전체 행사와 학년 공통 일정을 주간 슬롯에 맞춰 함께 관리할 수 있습니다.",
            },
            {
                "icon": "🔗",
                "title": "반별 입력 링크와 공유",
                "description": "담임이 자기 반만 입력하는 링크와 확정본 읽기 전용 링크를 함께 운영할 수 있습니다.",
            },
            {
                "icon": "🗓️",
                "title": "날짜별 예외 일정",
                "description": "특강, 대체수업, 12주차 일정처럼 특정 날짜만 다른 시간표를 따로 관리할 수 있습니다.",
            },
            {
                "icon": "🧾",
                "title": "검토와 운영 현황",
                "description": "반별 입력 현황, 검토 필요 반, 최근 활동을 보면서 확정 가능한 상태를 바로 확인할 수 있습니다.",
            },
        ]

        for item in feature_specs:
            feature, created_feature = ProductFeature.objects.get_or_create(
                product=product,
                title=item["title"],
                defaults={
                    "icon": item["icon"],
                    "description": item["description"],
                },
            )
            if not created_feature:
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
                "title": "우리학교 시간표 사용 가이드",
                "description": "학년 시간표 생성부터 반별 입력 링크 배포, 날짜별 예외 일정, 복원과 확정까지 바로 따라갈 수 있습니다.",
                "is_published": True,
            },
        )

        manual_changed = []
        manual_title = "우리학교 시간표 사용 가이드"
        if manual.title != manual_title:
            manual.title = manual_title
            manual_changed.append("title")
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        manual_desc = "학년 시간표 생성부터 공통 행사 입력, 반별 입력 링크 배포, 검토, 날짜별 예외 일정, 복원과 확정까지 바로 따라갈 수 있습니다."
        if manual.description != manual_desc:
            manual.description = manual_desc
            manual_changed.append("description")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        sections = [
            (
                "시작하기",
                "학교급과 학기 범위를 정하고 학년별 반 수를 입력하면 학년 시간표와 반별 입력 링크가 함께 만들어집니다.",
                1,
            ),
            (
                "반별 입력 링크 배포",
                "관리 교사는 반별 입력 현황에서 링크를 복사해 담임에게 전달하고, 입력 완료, 검토 필요, 마지막 저장과 링크 상태를 한 화면에서 확인할 수 있습니다.",
                2,
            ),
            (
                "공통 행사와 날짜별 일정",
                "학교 전체 행사나 학년 공통 행사를 넣고, 반별 링크에서는 특강·대체수업처럼 특정 날짜만 다른 예외 일정을 따로 저장할 수 있습니다.",
                3,
            ),
            (
                "검토와 확정",
                "겹침 경고, 검토 필요 반, 최근 활동을 확인하고 스냅샷으로 되돌릴 수 있으며, 확정하면 반별·교사별 읽기 전용 링크가 생성됩니다.",
                4,
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
                changed = []
                if section.content != content:
                    section.content = content
                    changed.append("content")
                if section.display_order != order:
                    section.display_order = order
                    changed.append("display_order")
                if changed:
                    section.save(update_fields=changed)

        self.stdout.write(self.style.SUCCESS("ensure_timetable completed"))
