from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure Fairy games products exist in database"

    def upsert_product(self, *, title, defaults, features, manual_title, manual_desc, sections):
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

        product, created = Product.objects.get_or_create(title=title, defaults=defaults)
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created product: {title}"))
        else:
            changed = []
            for field in mutable_fields:
                if getattr(product, field) != defaults[field]:
                    setattr(product, field, defaults[field])
                    changed.append(field)
            if changed:
                product.save(update_fields=changed)
                self.stdout.write(self.style.SUCCESS(f"Updated product fields: {title} ({', '.join(changed)})"))

        used_feature_ids = set()
        for item in features:
            feature = (
                ProductFeature.objects.filter(product=product, title=item["title"])
                .exclude(id__in=used_feature_ids)
                .order_by("id")
                .first()
            )
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
                    icon=item["icon"],
                    title=item["title"],
                    description=item["description"],
                )
            else:
                changed = []
                if feature.icon != item["icon"]:
                    feature.icon = item["icon"]
                    changed.append("icon")
                if feature.title != item["title"]:
                    feature.title = item["title"]
                    changed.append("title")
                if feature.description != item["description"]:
                    feature.description = item["description"]
                    changed.append("description")
                if changed:
                    feature.save(update_fields=changed)
            used_feature_ids.add(feature.id)

        stale_features = ProductFeature.objects.filter(product=product).exclude(id__in=used_feature_ids)
        if stale_features.exists():
            stale_features.delete()

        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": manual_title,
                "description": manual_desc,
                "is_published": True,
            },
        )
        changed_manual = []
        if manual.title != manual_title:
            manual.title = manual_title
            changed_manual.append("title")
        if not manual.is_published:
            manual.is_published = True
            changed_manual.append("is_published")
        if manual.description != manual_desc:
            manual.description = manual_desc
            changed_manual.append("description")
        if changed_manual:
            manual.save(update_fields=changed_manual)

        used_section_ids = set()
        for item in sections:
            section = (
                ManualSection.objects.filter(manual=manual, title=item["title"])
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
        if stale_sections.exists():
            stale_sections.delete()

    def handle(self, *args, **options):
        common_defaults = {
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "card_size": "small",
            "service_type": "game",
        }

        variants = [
            ("동물 장기", "🦁", "작은 판에서 사자를 지키며 빠르게 수 읽기를 익히는", "fairy_games:play_dobutsu", 17),
            ("커넥트 포", "🟡", "칩 4개를 먼저 한 줄로 연결하는", "fairy_games:play_cfour", 18),
            ("이솔레이션", "🧱", "이동 후 칸을 막아 상대를 가두는", "fairy_games:play_isolation", 19),
            ("아택스", "⚔", "복제와 점프로 세력을 넓히는", "fairy_games:play_ataxx", 20),
            ("브레이크스루", "🏁", "말 하나를 끝줄까지 먼저 돌파시키는", "fairy_games:play_breakthrough", 21),
            ("리버시", "⚫", "검은 돌과 흰 돌을 뒤집어 더 많은 칸을 차지하는", "fairy_games:play_reversi", 23),
        ]
        for title, icon, summary, route_name, order in variants:
            self.upsert_product(
                title=title,
                defaults={
                    **common_defaults,
                    "lead_text": f"{title} 로컬 대결을 바로 시작",
                    "description": f"{summary} 로컬 전략 게임입니다. 같은 화면에서 번갈아 두며 전략을 익힐 수 있습니다.",
                    "icon": icon,
                    "color_theme": "green",
                    "display_order": order,
                    "external_url": "",
                    "launch_route_name": route_name,
                },
                features=[
                    {"icon": "👥", "title": "로컬 대결", "description": "같은 화면에서 번갈아 두는 2인 모드"},
                    {"icon": "📘", "title": "규칙 요약", "description": "핵심 규칙과 승리 조건을 바로 확인"},
                    {"icon": "🏫", "title": "수업 활용", "description": "쉬는 시간과 전략 활동 도입에 바로 쓰기 좋음"},
                ],
                manual_title=f"{title} 사용 가이드",
                manual_desc=f"{title} 시작, 규칙 확인, 로컬 대결 흐름을 바로 확인할 수 있습니다.",
                sections=[
                    {"title": "시작하기", "content": "학생 게임 포털이나 서비스 카드에서 해당 게임을 열고 바로 시작합니다.", "display_order": 1},
                    {"title": "로컬 대결", "content": "같은 화면에서 두 플레이어가 번갈아 두는 로컬 전용 게임입니다.", "display_order": 2},
                    {"title": "수업 활용 팁", "content": "한 판이 짧아 쉬는 시간, 전략 활동, 두뇌 워밍업 용도로 활용하기 좋습니다.", "display_order": 3},
                ],
            )

        self.stdout.write(self.style.SUCCESS("ensure_fairy_games completed"))
