from django.db import migrations


def _first_non_empty_line(text):
    if not text:
        return ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _manual_description(product):
    base = _first_non_empty_line(product.lead_text) or _first_non_empty_line(product.description)
    if not base:
        return f"{product.title}를 빠르게 시작할 수 있도록 핵심 사용 흐름을 정리했습니다."
    if len(base) <= 180:
        return base
    return f"{base[:177]}..."


def create_missing_manuals(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ServiceManual = apps.get_model("products", "ServiceManual")
    ManualSection = apps.get_model("products", "ManualSection")

    active_products = Product.objects.filter(is_active=True).order_by("display_order")

    for product in active_products:
        manual, created = ServiceManual.objects.get_or_create(
            product=product,
            defaults={
                "title": f"{product.title} 이용방법",
                "description": _manual_description(product),
                "is_published": True,
            },
        )

        # Existing manuals are admin-managed data. Do not overwrite.
        if not created:
            continue

        start_link = product.external_url or "/"
        ManualSection.objects.create(
            manual=manual,
            title="1) 시작하기",
            content=(
                f"1. 서비스에 접속합니다: {start_link}\n"
                "2. 첫 화면에서 제공되는 핵심 버튼(시작하기/새로 만들기)을 눌러 기본 흐름을 확인합니다.\n"
                "3. 첫 실행에서는 1개의 작업만 완료해보며 화면 구성을 익힙니다.\n\n"
                "Tip: 처음에는 기능을 많이 켜기보다, 기본 동선부터 익히면 빠르게 적응할 수 있습니다."
            ),
            layout_type="text_only",
            badge_text="Step 1",
            display_order=1,
        )
        ManualSection.objects.create(
            manual=manual,
            title="2) 교실 적용 흐름",
            content=(
                "1. 오늘 수업/학급 운영에서 필요한 목표를 1개 정합니다.\n"
                "2. 해당 목표에 맞는 기능을 1~2개만 선택해 실행합니다.\n"
                "3. 결과를 학생/동료와 공유하고 다음 시간에 반영할 점을 기록합니다.\n\n"
                "예시: 공지 전달, 자료 수합, 학급 활동 기록처럼 반복 업무부터 적용하면 체감 효과가 큽니다."
            ),
            layout_type="card_carousel",
            badge_text="Step 2",
            display_order=2,
        )
        ManualSection.objects.create(
            manual=manual,
            title="3) 자주 묻는 질문",
            content=(
                "Q. 어디서 시작하면 좋을까요?\n"
                "A. 메인 화면의 첫 번째 핵심 기능부터 1회 실행해보세요.\n\n"
                "Q. 결과가 기대와 다를 때는 어떻게 하나요?\n"
                "A. 입력값(대상/기간/조건)을 좁혀 다시 실행하면 품질이 안정됩니다.\n\n"
                "Q. 운영 중 유의할 점은?\n"
                "A. 개인정보, 민감정보, 대외비 자료는 반드시 기관 지침에 따라 최소 범위로만 다뤄주세요."
            ),
            layout_type="text_only",
            badge_text="FAQ",
            display_order=3,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0029_rich_service_manuals"),
    ]

    operations = [
        migrations.RunPython(create_missing_manuals, migrations.RunPython.noop),
    ]
