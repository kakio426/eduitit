from django.db import migrations

def add_signatures_product(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    ProductFeature = apps.get_model('products', 'ProductFeature')

    # 모바일 연수 서명 서비스 생성
    signatures_product = Product.objects.create(
        title="연수 서명 관리",
        description="연수 현장에서 QR코드로 간편하게 참여자 서명을 받고 관리하는 서비스입니다. 종이 명부 없이 스마트하게 운영하세요.",
        price=0,
        is_active=True,
        is_featured=False,
        icon="fa-solid fa-pen-nib",
        color_theme="purple",
        card_size="small",
        display_order=2,
        service_type="tool",
        external_url="/signatures/",
    )

    # 주요 기능 추가
    features = [
        {
            "icon": "fa-solid fa-qrcode",
            "title": "간편 QR 서명",
            "description": "참여자가 자신의 스마트폰으로 QR을 찍어 즉석에서 서명을 남길 수 있습니다.",
        },
        {
            "icon": "fa-solid fa-file-export",
            "title": "서명부 출력 및 저장",
            "description": "수집된 서명을 정돈된 양식으로 확인하고 필요시 인쇄하거나 디지털로 보관합니다.",
        },
        {
            "icon": "fa-solid fa-shield-halved",
            "title": "안전한 데이터 관리",
            "description": "생성자만 서명 목록을 관리하고 삭제할 수 있어 보안이 철저합니다.",
        },
    ]

    for feature in features:
        ProductFeature.objects.create(product=signatures_product, **feature)


def remove_signatures_product(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    Product.objects.filter(title="연수 서명 관리").delete()


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0011_add_dutyticker_product'),
    ]

    operations = [
        migrations.RunPython(add_signatures_product, remove_signatures_product),
    ]
