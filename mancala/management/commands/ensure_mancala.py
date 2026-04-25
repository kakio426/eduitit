from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure Mancala product exists in database"

    def handle(self, *args, **options):
        title = "만칼라"
        defaults = {
            "lead_text": "씨앗을 나누며 셈과 전략을 익히는 3D 보드 게임입니다.",
            "description": (
                "만칼라는 씨앗을 하나씩 나누어 담으며 수 세기, 분배, 전략을 함께 연습하는 교실 활동 게임입니다. "
                "3D 보드, 이동 경로 강조, OpenSpiel 기반 AI 대전을 지원합니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "🏺",
            "color_theme": "green",
            "card_size": "small",
            "display_order": 24,
            "service_type": "game",
            "external_url": "",
            "launch_route_name": "mancala:main",
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

        product, created = Product.objects.get_or_create(title=title, defaults=defaults)
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

        self._sync_features(
            product,
            [
                {"icon": "🧮", "title": "분배와 셈", "description": "씨앗을 하나씩 나누며 수량 변화를 바로 봅니다."},
                {"icon": "✨", "title": "3D 경로", "description": "선택한 구멍의 이동 경로를 보드 위에 강조합니다."},
                {"icon": "🤖", "title": "AI 대전", "description": "OpenSpiel MCTS AI와 바로 한 판을 둡니다."},
            ],
        )
        self._sync_manual(product)

        self.stdout.write(self.style.SUCCESS("ensure_mancala completed"))

    def _sync_features(self, product, features):
        used_ids = set()
        for item in features:
            feature = (
                ProductFeature.objects.filter(product=product, title=item["title"])
                .exclude(id__in=used_ids)
                .order_by("id")
                .first()
            )
            if feature is None:
                feature = (
                    ProductFeature.objects.filter(product=product)
                    .exclude(id__in=used_ids)
                    .order_by("id")
                    .first()
                )
            if feature is None:
                feature = ProductFeature.objects.create(product=product, **item)
            else:
                changed = []
                for field in ("icon", "title", "description"):
                    if getattr(feature, field) != item[field]:
                        setattr(feature, field, item[field])
                        changed.append(field)
                if changed:
                    feature.save(update_fields=changed)
            used_ids.add(feature.id)

        ProductFeature.objects.filter(product=product).exclude(id__in=used_ids).delete()

    def _sync_manual(self, product):
        manual_title = "만칼라 사용 가이드"
        manual_desc = "시작, 씨뿌리기, AI 대전 흐름을 확인합니다."
        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": manual_title,
                "description": manual_desc,
                "is_published": True,
            },
        )
        changed = []
        if manual.title != manual_title:
            manual.title = manual_title
            changed.append("title")
        if manual.description != manual_desc:
            manual.description = manual_desc
            changed.append("description")
        if not manual.is_published:
            manual.is_published = True
            changed.append("is_published")
        if changed:
            manual.save(update_fields=changed)

        sections = [
            {"title": "시작하기", "content": "서비스 카드에서 만칼라를 열면 바로 새 판이 시작됩니다.", "display_order": 1},
            {"title": "씨뿌리기", "content": "내 구멍을 고르면 씨앗이 다음 구멍으로 하나씩 이동합니다.", "display_order": 2},
            {"title": "AI 대전", "content": "AI 대전이 켜져 있으면 내 수 뒤에 AI가 이어서 둡니다.", "display_order": 3},
        ]
        used_ids = set()
        for item in sections:
            section = (
                ManualSection.objects.filter(manual=manual, title=item["title"])
                .exclude(id__in=used_ids)
                .order_by("display_order", "id")
                .first()
            )
            if section is None:
                section = (
                    ManualSection.objects.filter(manual=manual, display_order=item["display_order"])
                    .exclude(id__in=used_ids)
                    .order_by("id")
                    .first()
                )
            if section is None:
                section = ManualSection.objects.create(manual=manual, **item)
            else:
                changed = []
                for field in ("title", "content", "display_order"):
                    if getattr(section, field) != item[field]:
                        setattr(section, field, item[field])
                        changed.append(field)
                if changed:
                    section.save(update_fields=changed)
            used_ids.add(section.id)

        ManualSection.objects.filter(manual=manual).exclude(id__in=used_ids).delete()
