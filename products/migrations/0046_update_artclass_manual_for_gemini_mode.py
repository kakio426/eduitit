from django.db import migrations


MANUAL_TITLE = "몽글몽글 미술 수업 이용방법"
PRODUCT_TITLE = "몽글몽글 미술 수업"
MANUAL_DESCRIPTION = "Gemini 수동 복붙으로 단계를 만들고 편집하는 실제 사용 순서로 안내합니다."

SECTIONS = [
    {
        "display_order": 0,
        "title": "Gemini 프롬프트 준비",
        "badge_text": "Step 1",
        "layout_type": "text_only",
        "content": (
            "1. /artclass/ 에서 유튜브 영상 URL을 입력합니다.\n"
            "2. 프롬프트용 대상 영상 URL 칸에 URL을 확인하거나 메인 주소 불러오기를 누릅니다.\n"
            "3. 프롬프트 복사 버튼으로 Gemini 지시문을 복사합니다."
        ),
    },
    {
        "display_order": 1,
        "title": "결과 붙여넣기 및 검증",
        "badge_text": "Step 2",
        "layout_type": "text_only",
        "content": (
            "1. Gemini에서 생성한 JSON 결과를 결과 붙여넣기 칸에 넣고 적용을 누릅니다.\n"
            "2. 파서가 형식을 점검해 단계 목록으로 반영합니다.\n"
            "3. 단계는 6~12개를 권장하며 24개 초과 시 앞 24개만 자동 반영됩니다."
        ),
    },
    {
        "display_order": 2,
        "title": "단계 편집 및 수업 실행",
        "badge_text": "Step 3",
        "layout_type": "text_only",
        "content": (
            "1. 단계 추가/삭제, 이미지 첨부, 클립보드 붙여넣기로 수업안을 다듬습니다.\n"
            "2. 자동 전환 간격(초)을 설정한 뒤 수업 시작하기를 누릅니다.\n"
            "3. 라이브러리에서 다른 선생님의 공유 수업도 참고할 수 있습니다."
        ),
    },
]


def update_artclass_manual(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ServiceManual = apps.get_model("products", "ServiceManual")
    ManualSection = apps.get_model("products", "ManualSection")

    product = Product.objects.filter(title=PRODUCT_TITLE).first()
    if not product:
        return

    manual, _ = ServiceManual.objects.get_or_create(
        product=product,
        defaults={
            "title": MANUAL_TITLE,
            "description": MANUAL_DESCRIPTION,
            "is_published": True,
        },
    )

    manual_changed = []
    if manual.title != MANUAL_TITLE:
        manual.title = MANUAL_TITLE
        manual_changed.append("title")
    if manual.description != MANUAL_DESCRIPTION:
        manual.description = MANUAL_DESCRIPTION
        manual_changed.append("description")
    if manual_changed:
        manual.save(update_fields=manual_changed)

    keep_orders = []
    for section_payload in SECTIONS:
        display_order = section_payload["display_order"]
        keep_orders.append(display_order)
        ManualSection.objects.update_or_create(
            manual=manual,
            display_order=display_order,
            defaults={
                "title": section_payload["title"],
                "content": section_payload["content"],
                "badge_text": section_payload["badge_text"],
                "layout_type": section_payload["layout_type"],
            },
        )

    ManualSection.objects.filter(manual=manual).exclude(display_order__in=keep_orders).delete()


def noop_reverse(apps, schema_editor):
    # Keep latest manual content on rollback.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0045_deactivate_legacy_insight_product"),
    ]

    operations = [
        migrations.RunPython(update_artclass_manual, noop_reverse),
    ]
