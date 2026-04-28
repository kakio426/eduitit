from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure Bamboo product and manual exist"

    def handle(self, *args, **options):
        product = self._sync_product()
        self._sync_features(product)
        self._sync_manual(product)
        self.stdout.write(self.style.SUCCESS("ensure_bamboo completed"))

    def _sync_product(self):
        title = "교사 대나무숲"
        defaults = {
            "lead_text": "속상한 일을 안전한 동물 우화로 바꿉니다.",
            "description": "실명과 학교명을 마스킹한 뒤 풍자 우화로 변환하는 교사용 리프레시 서비스입니다.",
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": True,
            "icon": "🎋",
            "color_theme": "green",
            "card_size": "small",
            "display_order": 33,
            "service_type": "counsel",
            "external_url": "",
            "launch_route_name": "bamboo:feed",
        }
        mutable_fields = list(defaults.keys())
        product, created = Product.objects.get_or_create(title=title, defaults=defaults)
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created product: {product.title}"))
            return product

        changed = []
        for field in mutable_fields:
            value = defaults[field]
            if getattr(product, field) != value:
                setattr(product, field, value)
                changed.append(field)
        if changed:
            product.save(update_fields=changed)
            self.stdout.write(self.style.SUCCESS(f"Updated product fields: {', '.join(changed)}"))
        return product

    def _sync_features(self, product):
        features = [
            {"icon": "🛡️", "title": "3중 안전", "description": "입력, 프롬프트, 출력에서 식별 정보를 막습니다."},
            {"icon": "🦊", "title": "풍자 우화", "description": "답답한 장면을 동물 우화로 바꿉니다."},
            {"icon": "🌿", "title": "익명 피드", "description": "검증된 우화만 익명으로 나눕니다."},
        ]
        used_ids = set()
        for item in features:
            feature = (
                ProductFeature.objects.filter(product=product, title=item["title"])
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
        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": "교사 대나무숲 사용 가이드",
                "description": "익명 사연을 안전하게 우화로 바꾸는 흐름입니다.",
                "is_published": True,
            },
        )
        changed = []
        if manual.title != "교사 대나무숲 사용 가이드":
            manual.title = "교사 대나무숲 사용 가이드"
            changed.append("title")
        if manual.description != "익명 사연을 안전하게 우화로 바꾸는 흐름입니다.":
            manual.description = "익명 사연을 안전하게 우화로 바꾸는 흐름입니다."
            changed.append("description")
        if not manual.is_published:
            manual.is_published = True
            changed.append("is_published")
        if changed:
            manual.save(update_fields=changed)

        sections = [
            {"title": "쓰기", "content": "속상한 일을 200자 안에 적고 우화로 변환합니다.", "display_order": 1},
            {"title": "안전", "content": "실명, 학교명, 지역, 연락처는 저장 전에 마스킹됩니다.", "display_order": 2},
            {"title": "공개", "content": "공개된 우화도 신고 1건이 들어오면 바로 내려갑니다.", "display_order": 3},
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
