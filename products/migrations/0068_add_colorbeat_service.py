from django.db import migrations


PRODUCT_TITLE = "알록달록 비트메이커"
LAUNCH_ROUTE = "colorbeat:main"


PRODUCT_DEFAULTS = {
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
    "launch_route_name": LAUNCH_ROUTE,
}

FEATURES = [
    {"icon": "8", "title": "8칸 비트", "description": "4개 소리를 8칸 그리드에 찍어 바로 재생"},
    {"icon": "♪", "title": "소리 세트", "description": "드럼, 반짝, 우주 소리를 한 번에 전환"},
    {"icon": "01", "title": "코드 보기", "description": "켜진 칸을 0과 1 배열로 확인"},
]

MANUAL = {
    "title": "알록달록 비트메이커 사용 가이드",
    "description": "비트 그리드, 소리 전환, 코드 보기 흐름을 확인합니다.",
    "is_published": True,
}

SECTIONS = [
    {"title": "시작", "content": "서비스 카드에서 알록달록 비트메이커를 열면 바로 그리드가 보입니다.", "display_order": 1},
    {"title": "비트", "content": "칸을 누르면 소리가 켜지고 재생 중인 박자가 밝게 표시됩니다.", "display_order": 2},
    {"title": "코드", "content": "코드 버튼으로 현재 비트를 0과 1 배열로 확인합니다.", "display_order": 3},
]


def _sync_features(ProductFeature, product):
    used_ids = set()
    for item in FEATURES:
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


def _sync_manual(ServiceManual, ManualSection, product):
    manual, _ = ServiceManual.objects.get_or_create(product=product, defaults=MANUAL)
    changed = []
    for field, value in MANUAL.items():
        if getattr(manual, field) != value:
            setattr(manual, field, value)
            changed.append(field)
    if changed:
        manual.save(update_fields=changed)

    used_ids = set()
    for item in SECTIONS:
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


def add_colorbeat_service(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ProductFeature = apps.get_model("products", "ProductFeature")
    ServiceManual = apps.get_model("products", "ServiceManual")
    ManualSection = apps.get_model("products", "ManualSection")

    product = (
        Product.objects.filter(launch_route_name=LAUNCH_ROUTE).order_by("id").first()
        or Product.objects.filter(title=PRODUCT_TITLE).order_by("id").first()
    )
    if product is None:
        product = Product.objects.create(title=PRODUCT_TITLE, **PRODUCT_DEFAULTS)
    else:
        changed = []
        if product.title != PRODUCT_TITLE:
            product.title = PRODUCT_TITLE
            changed.append("title")
        for field, value in PRODUCT_DEFAULTS.items():
            if getattr(product, field) != value:
                setattr(product, field, value)
                changed.append(field)
        if changed:
            product.save(update_fields=changed)

    _sync_features(ProductFeature, product)
    _sync_manual(ServiceManual, ManualSection, product)


def remove_colorbeat_service(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    Product.objects.filter(launch_route_name=LAUNCH_ROUTE).delete()
    Product.objects.filter(title=PRODUCT_TITLE).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0067_rollback_reservations_title"),
    ]

    operations = [
        migrations.RunPython(add_colorbeat_service, remove_colorbeat_service),
    ]
