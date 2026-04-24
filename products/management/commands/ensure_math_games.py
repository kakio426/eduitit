from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure math strategy games product exists in database"

    def handle(self, *args, **options):
        title = "수학 전략 게임"
        defaults = {
            "lead_text": "님과 24 게임을 바로 여는 수학 전략 활동입니다.",
            "description": "AI와 겨루는 님, 사칙연산으로 24를 만드는 퍼즐을 한 화면에서 시작합니다.",
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "🧮",
            "color_theme": "purple",
            "card_size": "small",
            "display_order": 24,
            "service_type": "game",
            "external_url": "",
            "launch_route_name": "math_games:index",
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
                if getattr(product, field) != defaults[field]:
                    setattr(product, field, defaults[field])
                    changed.append(field)
            if changed:
                product.save(update_fields=changed)
                self.stdout.write(self.style.SUCCESS(f"Updated product fields: {', '.join(changed)}"))

        self._sync_features(
            product,
            [
                {"icon": "N", "title": "님", "description": "더미에서 1~3개를 가져가는 AI 전략 대결"},
                {"icon": "24", "title": "24 게임", "description": "숫자 4개와 사칙연산으로 24 만들기"},
                {"icon": "?", "title": "힌트", "description": "AI의 생각과 풀이 힌트를 짧게 확인"},
            ],
        )
        self._sync_manual(
            product,
            "수학 전략 게임 사용 가이드",
            "게임 선택, AI 대결, 24 풀이 흐름을 확인합니다.",
            [
                ("시작하기", "서비스 카드에서 수학 전략 게임을 열고 게임을 고릅니다.", 1),
                ("님", "더미 하나를 골라 1~3개를 가져갑니다. 마지막을 가져가면 승리입니다.", 2),
                ("24 게임", "숫자 4개를 한 번씩 쓰고 사칙연산으로 24를 만듭니다.", 3),
            ],
        )
        self.stdout.write(self.style.SUCCESS("ensure_math_games completed"))

    def _sync_features(self, product, feature_specs):
        used_feature_ids = set()
        for item in feature_specs:
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
                feature = ProductFeature.objects.create(product=product, **item)
            else:
                changed = []
                for field in ["icon", "title", "description"]:
                    if getattr(feature, field) != item[field]:
                        setattr(feature, field, item[field])
                        changed.append(field)
                if changed:
                    feature.save(update_fields=changed)
            used_feature_ids.add(feature.id)
        ProductFeature.objects.filter(product=product).exclude(id__in=used_feature_ids).delete()

    def _sync_manual(self, product, title, description, section_specs):
        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": title,
                "description": description,
                "is_published": True,
            },
        )
        manual_changed = []
        if manual.title != title:
            manual.title = title
            manual_changed.append("title")
        if manual.description != description:
            manual.description = description
            manual_changed.append("description")
        if not manual.is_published:
            manual.is_published = True
            manual_changed.append("is_published")
        if manual_changed:
            manual.save(update_fields=manual_changed)

        used_section_ids = set()
        for section_title, content, order in section_specs:
            section = (
                ManualSection.objects.filter(manual=manual, title=section_title)
                .exclude(id__in=used_section_ids)
                .order_by("display_order", "id")
                .first()
            )
            if section is None:
                section = (
                    ManualSection.objects.filter(manual=manual, display_order=order)
                    .exclude(id__in=used_section_ids)
                    .order_by("id")
                    .first()
                )
            if section is None:
                section = ManualSection.objects.create(
                    manual=manual,
                    title=section_title,
                    content=content,
                    display_order=order,
                )
            else:
                changed = []
                if section.title != section_title:
                    section.title = section_title
                    changed.append("title")
                if section.content != content:
                    section.content = content
                    changed.append("content")
                if section.display_order != order:
                    section.display_order = order
                    changed.append("display_order")
                if changed:
                    section.save(update_fields=changed)
            used_section_ids.add(section.id)
        ManualSection.objects.filter(manual=manual).exclude(id__in=used_section_ids).delete()
