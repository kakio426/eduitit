from django.db import migrations


COMMON_FAIRY_FEATURES = [
    {"icon": "👥", "title": "로컬 대결", "description": "같은 화면에서 번갈아 두는 2인 모드"},
    {"icon": "📘", "title": "규칙 요약", "description": "핵심 규칙과 승리 조건을 바로 확인"},
    {"icon": "🏫", "title": "수업 활용", "description": "쉬는 시간과 전략 활동 도입에 바로 쓰기 좋음"},
]

COMMON_FAIRY_SECTIONS = [
    {
        "title": "시작하기",
        "content": "학생 게임 포털이나 서비스 카드에서 해당 게임을 열고 바로 시작합니다.",
        "display_order": 1,
    },
    {
        "title": "로컬 대결",
        "content": "같은 화면에서 두 플레이어가 번갈아 두는 로컬 전용 게임입니다.",
        "display_order": 2,
    },
    {
        "title": "수업 활용 팁",
        "content": "한 판이 짧아 쉬는 시간, 전략 활동, 두뇌 워밍업 용도로 활용하기 좋습니다.",
        "display_order": 3,
    },
]

GAME_PRODUCT_SPECS = [
    {
        "title": "두뇌 풀가동! 교실 체스",
        "aliases": ["두뇌 풀가동! 교실 체스", "체스"],
        "defaults": {
            "lead_text": "준비물 없이 한 화면 대전과 AI 연습을 바로 시작하는 교실 체스입니다.",
            "description": "두뇌 풀가동! 교실 체스는 같은 화면에서 친구와 번갈아 두는 로컬 대전과 Stockfish 기반 AI 대전을 모두 지원하는 체스 서비스입니다. 규칙 보기와 플레이 진입 경로를 분리해 수업 중에도 안정적으로 시작할 수 있습니다.",
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "♟️",
            "color_theme": "dark",
            "card_size": "small",
            "display_order": 14,
            "service_type": "game",
            "external_url": "",
            "launch_route_name": "chess:index",
        },
        "features": [
            {
                "icon": "🤖",
                "title": "무료 AI 대전 (Stockfish)",
                "description": "세계 최강급 AI 엔진 Stockfish.js를 탑재했습니다. 4단계 난이도로 실력에 맞춰 연습할 수 있습니다.",
            },
            {
                "icon": "🤝",
                "title": "1대1 로컬 대전",
                "description": "친구와 한 화면에서 번갈아 두는 로컬 대전을 지원합니다.",
            },
            {
                "icon": "📜",
                "title": "규칙 가이드",
                "description": "체스 말 이동, 특수 규칙, 시작 흐름을 빠르게 확인할 수 있습니다.",
            },
        ],
        "manual": {
            "title": "교실 체스 사용법",
            "description": "로컬 대전, AI 대전, 규칙 보기 흐름을 바로 따라갈 수 있습니다.",
        },
        "sections": [
            {
                "title": "시작하기",
                "content": "교실 체스를 열고 로컬 대전 또는 AI 대전을 선택해 시작합니다.",
                "display_order": 1,
            },
            {
                "title": "AI 대전",
                "content": "easy, medium, hard, expert 4단계 난이도 중 하나를 골라 AI와 대전합니다.",
                "display_order": 2,
            },
            {
                "title": "규칙 가이드",
                "content": "규칙 보기 화면에서 말 이동과 특수 규칙을 먼저 익힌 뒤 플레이하면 안정적으로 시작할 수 있습니다.",
                "display_order": 3,
            },
        ],
    },
    {
        "title": "두뇌 풀가동! 교실 장기",
        "aliases": ["두뇌 풀가동! 교실 장기", "장기"],
        "defaults": {
            "lead_text": "준비물 없이 한 화면 대전과 AI 연습을 바로 시작하는 교실 장기입니다.",
            "description": "두뇌 풀가동! 교실 장기는 같은 화면에서 번갈아 두는 로컬 대전과 브라우저 AI 연습을 지원하는 전통 전략 게임입니다. 규칙 보기와 플레이 진입 경로를 분리해 수업 중에도 안정적으로 시작할 수 있습니다.",
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "🧠",
            "color_theme": "dark",
            "card_size": "small",
            "display_order": 15,
            "service_type": "game",
            "external_url": "",
            "launch_route_name": "janggi:index",
        },
        "features": [
            {
                "icon": "🤝",
                "title": "한 화면 로컬 대전",
                "description": "친구와 번갈아 두며 장기판 하나로 바로 대결합니다.",
            },
            {
                "icon": "🤖",
                "title": "AI 대전 구조",
                "description": "브라우저 기반 AI 상대와 실력에 맞춰 연습할 수 있습니다.",
            },
            {
                "icon": "📘",
                "title": "규칙 가이드",
                "description": "장기 말 이동과 기본 흐름을 짧게 확인하고 시작할 수 있습니다.",
            },
        ],
        "manual": {
            "title": "교실 장기 사용법",
            "description": "로컬 대전 시작부터 AI 모드 연결까지 바로 따라갈 수 있습니다.",
        },
        "sections": [
            {
                "title": "시작하기",
                "content": "교실 장기를 열고 로컬 대전 또는 AI 연습 흐름으로 시작합니다.",
                "display_order": 1,
            },
            {
                "title": "AI 모드 연결",
                "content": "AI 연습 모드에서는 브라우저 안에서 상대 수를 계산해 바로 대국을 이어갑니다.",
                "display_order": 2,
            },
            {
                "title": "수업 활용 팁",
                "content": "처음에는 로컬 대전으로 규칙을 익히고 이후 AI 난이도를 단계적으로 올리세요.",
                "display_order": 3,
            },
        ],
    },
    {
        "title": "동물 장기",
        "aliases": ["동물 장기"],
        "defaults": {
            "lead_text": "동물 장기 로컬 대결을 바로 시작",
            "description": "작은 판에서 사자를 지키며 빠르게 수 읽기를 익히는 로컬 전략 게임입니다. 같은 화면에서 번갈아 두며 전략을 익힐 수 있습니다.",
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "🦁",
            "color_theme": "green",
            "card_size": "small",
            "display_order": 17,
            "service_type": "game",
            "external_url": "",
            "launch_route_name": "fairy_games:play_dobutsu",
        },
        "features": COMMON_FAIRY_FEATURES,
        "manual": {
            "title": "동물 장기 사용 가이드",
            "description": "동물 장기 시작, 규칙 확인, 로컬 대결 흐름을 바로 확인할 수 있습니다.",
        },
        "sections": COMMON_FAIRY_SECTIONS,
    },
    {
        "title": "커넥트 포",
        "aliases": ["커넥트 포"],
        "defaults": {
            "lead_text": "커넥트 포 로컬 대결을 바로 시작",
            "description": "칩 4개를 먼저 한 줄로 연결하는 로컬 전략 게임입니다. 같은 화면에서 번갈아 두며 전략을 익힐 수 있습니다.",
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "🟡",
            "color_theme": "green",
            "card_size": "small",
            "display_order": 18,
            "service_type": "game",
            "external_url": "",
            "launch_route_name": "fairy_games:play_cfour",
        },
        "features": COMMON_FAIRY_FEATURES,
        "manual": {
            "title": "커넥트 포 사용 가이드",
            "description": "커넥트 포 시작, 규칙 확인, 로컬 대결 흐름을 바로 확인할 수 있습니다.",
        },
        "sections": COMMON_FAIRY_SECTIONS,
    },
    {
        "title": "이솔레이션",
        "aliases": ["이솔레이션"],
        "defaults": {
            "lead_text": "이솔레이션 로컬 대결을 바로 시작",
            "description": "이동 후 칸을 막아 상대를 가두는 로컬 전략 게임입니다. 같은 화면에서 번갈아 두며 전략을 익힐 수 있습니다.",
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "🧱",
            "color_theme": "green",
            "card_size": "small",
            "display_order": 19,
            "service_type": "game",
            "external_url": "",
            "launch_route_name": "fairy_games:play_isolation",
        },
        "features": COMMON_FAIRY_FEATURES,
        "manual": {
            "title": "이솔레이션 사용 가이드",
            "description": "이솔레이션 시작, 규칙 확인, 로컬 대결 흐름을 바로 확인할 수 있습니다.",
        },
        "sections": COMMON_FAIRY_SECTIONS,
    },
    {
        "title": "아택스",
        "aliases": ["아택스"],
        "defaults": {
            "lead_text": "아택스 로컬 대결을 바로 시작",
            "description": "복제와 점프로 세력을 넓히는 로컬 전략 게임입니다. 같은 화면에서 번갈아 두며 전략을 익힐 수 있습니다.",
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "⚔",
            "color_theme": "green",
            "card_size": "small",
            "display_order": 20,
            "service_type": "game",
            "external_url": "",
            "launch_route_name": "fairy_games:play_ataxx",
        },
        "features": COMMON_FAIRY_FEATURES,
        "manual": {
            "title": "아택스 사용 가이드",
            "description": "아택스 시작, 규칙 확인, 로컬 대결 흐름을 바로 확인할 수 있습니다.",
        },
        "sections": COMMON_FAIRY_SECTIONS,
    },
    {
        "title": "브레이크스루",
        "aliases": ["브레이크스루"],
        "defaults": {
            "lead_text": "브레이크스루 로컬 대결을 바로 시작",
            "description": "말 하나를 끝줄까지 먼저 돌파시키는 로컬 전략 게임입니다. 같은 화면에서 번갈아 두며 전략을 익힐 수 있습니다.",
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "🏁",
            "color_theme": "green",
            "card_size": "small",
            "display_order": 21,
            "service_type": "game",
            "external_url": "",
            "launch_route_name": "fairy_games:play_breakthrough",
        },
        "features": COMMON_FAIRY_FEATURES,
        "manual": {
            "title": "브레이크스루 사용 가이드",
            "description": "브레이크스루 시작, 규칙 확인, 로컬 대결 흐름을 바로 확인할 수 있습니다.",
        },
        "sections": COMMON_FAIRY_SECTIONS,
    },
    {
        "title": "탭 순발력 챌린지",
        "aliases": ["탭 순발력 챌린지"],
        "defaults": {
            "lead_text": "탭 신호를 보고 가장 빠르게 반응하는 교실용 반응속도 게임입니다.",
            "description": "탭 순발력 챌린지는 랜덤 신호를 기다렸다가 정확한 타이밍에 화면을 터치해 반응속도를 측정하는 교실 활동입니다. 싱글 기록 도전, 1:1 대결, 신호 전 터치 반칙 처리, 전체화면 모드를 지원합니다.",
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "⚡",
            "color_theme": "green",
            "card_size": "small",
            "display_order": 22,
            "service_type": "game",
            "external_url": "",
            "launch_route_name": "reflex_game:main",
        },
        "features": [
            {"icon": "⏱️", "title": "반응속도 측정", "description": "랜덤 신호 이후 탭 시간을 ms 단위로 표시합니다."},
            {"icon": "🚫", "title": "반칙 감지", "description": "탭 사인 전에 누르면 반칙으로 즉시 표시됩니다."},
            {"icon": "🖥️", "title": "전체화면 지원", "description": "교실 터치 스크린에서 몰입감 있게 진행할 수 있습니다."},
        ],
        "manual": {
            "title": "탭 순발력 챌린지 사용 가이드",
            "description": "시작, 반칙 규칙, 전체화면 활용을 바로 확인할 수 있습니다.",
        },
        "sections": [
            {
                "title": "시작하기",
                "content": "교실 활동에서 '탭 순발력 챌린지'를 누른 뒤 시작 버튼으로 게임을 시작합니다.",
                "display_order": 1,
            },
            {
                "title": "반칙 규칙",
                "content": "탭 신호(TAP) 전에 화면을 누르면 즉시 반칙으로 처리되어 기록이 인정되지 않습니다.",
                "display_order": 2,
            },
            {
                "title": "대결 운영",
                "content": "1:1 대결 모드에서 좌우 플레이어가 동시에 준비하고 신호 후 먼저 탭한 학생이 승리합니다.",
                "display_order": 3,
            },
        ],
    },
    {
        "title": "리버시",
        "aliases": ["리버시"],
        "defaults": {
            "lead_text": "리버시 로컬 대결을 바로 시작",
            "description": "검은 돌과 흰 돌을 뒤집어 더 많은 칸을 차지하는 로컬 전략 게임입니다. 같은 화면에서 번갈아 두며 전략을 익힐 수 있습니다.",
            "price": 0.00,
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "⚫",
            "color_theme": "green",
            "card_size": "small",
            "display_order": 23,
            "service_type": "game",
            "external_url": "",
            "launch_route_name": "fairy_games:play_reversi",
        },
        "features": COMMON_FAIRY_FEATURES,
        "manual": {
            "title": "리버시 사용 가이드",
            "description": "리버시 시작, 규칙 확인, 로컬 대결 흐름을 바로 확인할 수 있습니다.",
        },
        "sections": COMMON_FAIRY_SECTIONS,
    },
]


def _find_product(Product, aliases):
    for alias in aliases:
        product = Product.objects.filter(title=alias).order_by("id").first()
        if product is not None:
            return product
    return None


def _sync_product_fields(product, defaults):
    changed = []
    for field, value in defaults.items():
        if getattr(product, field) != value:
            setattr(product, field, value)
            changed.append(field)
    if changed:
        product.save(update_fields=changed)


def _sync_features(ProductFeature, product, feature_specs):
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

    ProductFeature.objects.filter(product=product).exclude(id__in=used_feature_ids).delete()


def _sync_manual(ServiceManual, ManualSection, product, manual_spec, section_specs):
    manual = ServiceManual.objects.filter(product=product).first()
    if manual is None:
        manual = ServiceManual.objects.create(
            product=product,
            title=manual_spec["title"],
            description=manual_spec["description"],
            is_published=True,
        )
    else:
        changed = []
        if manual.title != manual_spec["title"]:
            manual.title = manual_spec["title"]
            changed.append("title")
        if manual.description != manual_spec["description"]:
            manual.description = manual_spec["description"]
            changed.append("description")
        if not manual.is_published:
            manual.is_published = True
            changed.append("is_published")
        if changed:
            manual.save(update_fields=changed)

    used_section_ids = set()
    for item in section_specs:
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

    ManualSection.objects.filter(manual=manual).exclude(id__in=used_section_ids).delete()


def sync_game_service_menu(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ProductFeature = apps.get_model("products", "ProductFeature")
    ServiceManual = apps.get_model("products", "ServiceManual")
    ManualSection = apps.get_model("products", "ManualSection")

    for spec in GAME_PRODUCT_SPECS:
        product = _find_product(Product, spec["aliases"])
        if product is None:
            product = Product.objects.create(title=spec["title"], **spec["defaults"])
        else:
            if product.title != spec["title"]:
                product.title = spec["title"]
                product.save(update_fields=["title"])
            _sync_product_fields(product, spec["defaults"])

        _sync_features(ProductFeature, product, spec["features"])
        _sync_manual(ServiceManual, ManualSection, product, spec["manual"], spec["sections"])


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0057_add_infoboard_service"),
    ]

    operations = [
        migrations.RunPython(sync_game_service_menu, migrations.RunPython.noop),
    ]
