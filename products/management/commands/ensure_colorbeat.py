from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure colorbeat maker product exists in database"

    def handle(self, *args, **options):
        product = self._sync_product()
        self._sync_features(
            product,
            [
                {"icon": "8", "title": "8칸 비트", "description": "4개 소리를 8칸 그리드에 찍어 바로 재생"},
                {"icon": "♪", "title": "소리 세트", "description": "드럼, 반짝, 우주 소리를 한 번에 전환"},
                {"icon": "01", "title": "코드 보기", "description": "켜진 칸을 0과 1 배열로 확인"},
            ],
        )
        self._sync_manual(
            product,
            "알록달록 비트메이커 사용 가이드",
            "비트 그리드, 소리 전환, 코드 보기 흐름을 확인합니다.",
            [
                ("시작", "서비스 카드에서 알록달록 비트메이커를 열면 바로 그리드가 보입니다.", 1),
                ("비트", "칸을 누르면 소리가 켜지고 재생 중인 박자가 밝게 표시됩니다.", 2),
                ("코드", "코드 버튼으로 현재 비트를 0과 1 배열로 확인합니다.", 3),
            ],
        )
        self.stdout.write(self.style.SUCCESS("ensure_colorbeat completed"))

    def _sync_product(self):
        title = "알록달록 비트메이커"
        defaults = {
            "lead_text": "칸을 눌러 리듬을 만들고 숫자 배열로 확인하는 음악 코딩 활동입니다.",
            "description": (
                "알록달록 비트메이커는 4개 소리와 8개 박자 칸으로 리듬을 만드는 교실 음악 코딩 활동입니다. "
                "재생 바, 템포 조절, 랜덤 비트, 소리 세트, 0/1 코드 보기를 한 화면에서 제공합니다."
            ),
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "🎵",
            "color_theme": "orange",
            "card_size": "small",
            "display_order": 25,
            "service_type": "game",
            "external_url": "",
            "launch_route_name": "colorbeat:main",
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

        product = (
            Product.objects.filter(launch_route_name=defaults["launch_route_name"]).order_by("id").first()
            or Product.objects.filter(title=title).order_by("id").first()
        )
        if product is None:
            product = Product.objects.create(title=title, **defaults)
            self.stdout.write(self.style.SUCCESS(f"Created product: {product.title}"))
            return product

        changed = []
        if product.title != title:
            product.title = title
            changed.append("title")
        for field in mutable_fields:
            if getattr(product, field) != defaults[field]:
                setattr(product, field, defaults[field])
                changed.append(field)
        if changed:
            product.save(update_fields=changed)
            self.stdout.write(self.style.SUCCESS(f"Updated product fields: {', '.join(changed)}"))
        return product

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
                for field in ("icon", "title", "description"):
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
        changed = []
        if manual.title != title:
            manual.title = title
            changed.append("title")
        if manual.description != description:
            manual.description = description
            changed.append("description")
        if not manual.is_published:
            manual.is_published = True
            changed.append("is_published")
        if changed:
            manual.save(update_fields=changed)

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
