from django.db import migrations


PRODUCT_TITLE = "교사용 AI 법률 가이드"
LAUNCH_ROUTE = "teacher_law:main"


def seed_teacher_law_service(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ProductFeature = apps.get_model("products", "ProductFeature")
    ServiceManual = apps.get_model("products", "ServiceManual")
    ManualSection = apps.get_model("products", "ManualSection")

    defaults = {
        "lead_text": "학교폭력, 사진 게시, 생활지도처럼 교실에서 바로 확인해야 할 법령만 빠르게 정리합니다.",
        "description": (
            "교사용 AI 법률 가이드는 국가법령정보 공식 API를 바탕으로 교사가 자주 묻는 학교 현장 질문을 정리해 주는 서비스입니다. "
            "질문마다 관련 조문, 공식 출처, 조회 시각을 함께 보여 주고, 고위험 사안은 사람 상담이 더 필요하다는 안내를 함께 제공합니다."
        ),
        "price": 0.00,
        "is_active": True,
        "is_featured": False,
        "is_guest_allowed": False,
        "icon": "⚖️",
        "color_theme": "blue",
        "card_size": "small",
        "display_order": 18,
        "service_type": "edutech",
        "external_url": "",
        "launch_route_name": LAUNCH_ROUTE,
        "solve_text": "교실에서 바로 확인할 법령 근거가 필요해요",
        "result_text": "조문과 공식 출처가 함께 정리된 답변",
        "time_text": "1분 안팎",
    }

    product = Product.objects.filter(launch_route_name=LAUNCH_ROUTE).order_by("id").first()
    if not product:
        product = Product.objects.filter(title=PRODUCT_TITLE).order_by("id").first()

    if product is None:
        product = Product.objects.create(title=PRODUCT_TITLE, **defaults)
    else:
        changed_fields = []
        if not (product.launch_route_name or "").strip():
            product.launch_route_name = defaults["launch_route_name"]
            changed_fields.append("launch_route_name")
        if not (product.solve_text or "").strip():
            product.solve_text = defaults["solve_text"]
            changed_fields.append("solve_text")
        if not (product.result_text or "").strip():
            product.result_text = defaults["result_text"]
            changed_fields.append("result_text")
        if not (product.time_text or "").strip():
            product.time_text = defaults["time_text"]
            changed_fields.append("time_text")
        if not (product.lead_text or "").strip():
            product.lead_text = defaults["lead_text"]
            changed_fields.append("lead_text")
        if not (product.description or "").strip():
            product.description = defaults["description"]
            changed_fields.append("description")
        if not (product.icon or "").strip():
            product.icon = defaults["icon"]
            changed_fields.append("icon")
        if not product.is_active:
            product.is_active = True
            changed_fields.append("is_active")
        valid_service_types = {code for code, _ in Product.SERVICE_CHOICES}
        if product.service_type not in valid_service_types:
            product.service_type = defaults["service_type"]
            changed_fields.append("service_type")
        valid_color_themes = {code for code, _ in Product.COLOR_CHOICES}
        if product.color_theme not in valid_color_themes:
            product.color_theme = defaults["color_theme"]
            changed_fields.append("color_theme")
        if changed_fields:
            product.save(update_fields=list(dict.fromkeys(changed_fields)))

    features = [
        {
            "icon": "📚",
            "title": "공식 법령 근거 확인",
            "description": "국가법령정보 API를 조회해 질문과 관련된 법령명, 조문, 공식 출처를 함께 보여 줍니다.",
        },
        {
            "icon": "🛟",
            "title": "고위험 사안 분리 안내",
            "description": "아동학대 의심, 신체 제지, 개인정보 유출처럼 위험도가 높은 질문은 사람 상담 권고를 함께 표시합니다.",
        },
        {
            "icon": "⚡",
            "title": "빠른 질문 바로 시작",
            "description": "교사가 자주 묻는 질문은 빠른 버튼과 캐시 응답으로 더 빨리 다시 확인할 수 있습니다.",
        },
    ]
    for feature in features:
        ProductFeature.objects.update_or_create(
            product=product,
            title=feature["title"],
            defaults={
                "icon": feature["icon"],
                "description": feature["description"],
            },
        )

    manual, _ = ServiceManual.objects.get_or_create(
        product=product,
        defaults={
            "title": "교사용 AI 법률 가이드 사용법",
            "description": "질문 입력부터 근거 확인, 사람 상담이 더 필요한 경우까지 빠르게 따라가는 안내입니다.",
            "is_published": True,
        },
    )
    manual_changed = []
    if not (manual.title or "").strip():
        manual.title = "교사용 AI 법률 가이드 사용법"
        manual_changed.append("title")
    if not (manual.description or "").strip():
        manual.description = "질문 입력부터 근거 확인, 사람 상담이 더 필요한 경우까지 빠르게 따라가는 안내입니다."
        manual_changed.append("description")
    if not manual.is_published:
        manual.is_published = True
        manual_changed.append("is_published")
    if manual_changed:
        manual.save(update_fields=manual_changed)

    sections = [
        {
            "title": "무엇을 물을 수 있나요?",
            "content": "학교폭력, 사진·영상 게시, 개인정보, 생활지도, 학부모 민원, 신고 의무처럼 교실에서 바로 확인해야 할 질문을 먼저 적어 보세요.",
            "display_order": 1,
            "badge_text": "Step 1",
        },
        {
            "title": "답변은 어떻게 읽나요?",
            "content": "답변에는 핵심 정리, 지금 바로 할 일, 근거 조문, 공식 출처, 조회 시각이 함께 표시됩니다. 근거가 약하면 추가 확인 필요로 안내합니다.",
            "display_order": 2,
            "badge_text": "Step 2",
        },
        {
            "title": "언제 사람 상담이 필요한가요?",
            "content": "아동학대 의심, 신체 제지, 개인정보 유출, 형사 책임 우려처럼 위험도가 높은 사안은 학교 관리자나 전문 상담과 함께 진행해 주세요.",
            "display_order": 3,
            "badge_text": "Step 3",
        },
    ]
    for section in sections:
        ManualSection.objects.update_or_create(
            manual=manual,
            title=section["title"],
            defaults={
                "content": section["content"],
                "display_order": section["display_order"],
                "badge_text": section["badge_text"],
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0064_dttimeslot_morning_dtmissionautomation_slot_code"),
        ("teacher_law", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_teacher_law_service, migrations.RunPython.noop),
    ]
