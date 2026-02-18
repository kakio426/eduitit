from decimal import Decimal

from django.db import migrations


def add_parent_consent_product(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ProductFeature = apps.get_model("products", "ProductFeature")

    product, _ = Product.objects.get_or_create(
        title="동의서는 나에게 맡겨",
        defaults={
            "lead_text": "학부모 동의서 수합을 모바일 3단계로 간단하게 처리합니다.",
            "description": "문서 업로드, 링크 발송 시뮬레이션, 손서명 수합, 통합 PDF 다운로드까지 한 번에 제공합니다.",
            "price": Decimal("0.00"),
            "is_active": True,
            "is_featured": False,
            "is_guest_allowed": False,
            "icon": "fa-solid fa-file-signature",
            "color_theme": "purple",
            "card_size": "small",
            "display_order": 6,
            "service_type": "classroom",
            "external_url": "/consent/",
            "solve_text": "종이 동의서 회수 부담",
            "result_text": "모바일 수합 + PDF 증빙",
            "time_text": "약 3분",
        },
    )

    features = [
        ("fa-solid fa-mobile-screen-button", "학부모 3단계 위저드", "본인확인 → 동의/비동의+손서명 → 완료"),
        ("fa-solid fa-table-list", "교사용 테이블 대시보드", "수신자 상태와 발송 링크를 한 번에 관리"),
        ("fa-solid fa-file-pdf", "통합 PDF 생성", "학생명(가나다) 순서로 수합본을 다운로드"),
    ]
    for icon, title, description in features:
        ProductFeature.objects.get_or_create(
            product=product,
            title=title,
            defaults={"icon": icon, "description": description},
        )


def remove_parent_consent_product(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    Product.objects.filter(title="동의서는 나에게 맡겨").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0033_rename_latest_center_title"),
    ]

    operations = [
        migrations.RunPython(add_parent_consent_product, remove_parent_consent_product),
    ]
