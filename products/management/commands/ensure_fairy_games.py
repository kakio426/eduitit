from django.core.management.base import BaseCommand

from products.models import ManualSection, Product, ProductFeature, ServiceManual


class Command(BaseCommand):
    help = "Ensure Fairy games products exist in database"

    def upsert_product(self, *, title, defaults, features, manual_title, manual_desc):
        mutable_fields = [
            "lead_text",
            "description",
            "price",
            "is_active",
            "is_guest_allowed",
            "icon",
            "external_url",
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

        for icon, feature_title, desc in features:
            ProductFeature.objects.get_or_create(
                product=product,
                title=feature_title,
                defaults={"icon": icon, "description": desc},
            )

        manual, _ = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": manual_title,
                "description": manual_desc,
                "is_published": True,
            },
        )
        changed_manual = []
        if not manual.is_published:
            manual.is_published = True
            changed_manual.append("is_published")
        if not manual.description:
            manual.description = manual_desc
            changed_manual.append("description")
        if changed_manual:
            manual.save(update_fields=changed_manual)

        sections = [
            ("시작하기", "대시보드에서 해당 게임 카드를 눌러 바로 시작합니다.", 1),
            ("대결 모드", "로컬 대결 또는 AI 대결을 선택해 진행합니다.", 2),
            ("AI 난이도", "easy -> medium -> hard -> expert 순서로 학습합니다.", 3),
        ]
        for section_title, content, order in sections:
            section, created = ManualSection.objects.get_or_create(
                manual=manual,
                title=section_title,
                defaults={"content": content, "display_order": order},
            )
            if not created:
                changed = []
                if section.display_order != order:
                    section.display_order = order
                    changed.append("display_order")
                if section.content != content:
                    section.content = content
                    changed.append("content")
                if changed:
                    section.save(update_fields=changed)

    def handle(self, *args, **options):
        common_defaults = {
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "card_size": "small",
            "service_type": "game",
        }

        # 기존 묶음 카드는 데이터 보존을 위해 삭제하지 않고 비활성 처리
        Product.objects.filter(title="Fairy 전략 게임 5종").update(is_active=False)

        variants = [
            ("동물 장기", "🦁", "Dobutsu Shogi", "/fairy-games/dobutsu/play/?mode=local", 17),
            ("커넥트 포", "🟡", "Connect Four", "/fairy-games/cfour/play/?mode=local", 18),
            ("이솔레이션", "🧱", "Isolation", "/fairy-games/isolation/play/?mode=local", 19),
            ("아택스", "⚔", "Ataxx", "/fairy-games/ataxx/play/?mode=local", 20),
            ("브레이크스루", "🏁", "Breakthrough", "/fairy-games/breakthrough/play/?mode=local", 21),
        ]
        for title, icon, subtitle, url, order in variants:
            self.upsert_product(
                title=title,
                defaults={
                    **common_defaults,
                    "lead_text": f"{title} 게임을 로컬/AI 모드로 바로 시작",
                    "description": f"{subtitle} 규칙 기반 전략 게임입니다. 초등학생도 쉽게 시작할 수 있도록 구성했습니다.",
                    "icon": icon,
                    "color_theme": "green",
                    "display_order": order,
                    "external_url": url,
                },
                features=[
                    ("👥", "로컬 대결", "같은 화면에서 번갈아 두는 2인 모드"),
                    ("🤖", "AI 대결", "난이도 단계별 연습 모드"),
                    ("📘", "규칙 설명", "핵심 규칙을 쉽게 확인"),
                ],
                manual_title=f"{title} 사용 가이드",
                manual_desc=f"{title}의 시작 방법, 대결 모드, AI 난이도 선택 방법을 안내합니다.",
            )

        self.stdout.write(self.style.SUCCESS("ensure_fairy_games completed"))
