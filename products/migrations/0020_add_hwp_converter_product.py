# Generated manually - HWP to PDF 변환기 Product 등록

from django.db import migrations


def add_hwp_converter(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    ProductFeature = apps.get_model('products', 'ProductFeature')

    product = Product.objects.create(
        title='HWP to PDF 변환기',
        lead_text='한글 파일을 PDF로 간편하게 변환하세요 📄',
        description='한글(Hancom Office)의 OLE Automation 기능을 활용하여 HWP/HWPX 파일을 PDF로 빠르고 간편하게 변환하는 경량 데스크톱 프로그램입니다. 정품 한글이 설치된 Windows 환경에서 작동하며, 별도의 서버 없이 로컬에서 바로 실행됩니다.\n\n[주의사항]\n- 본 프로그램의 상업적 목적의 재배포를 금지합니다.\n- 본 프로그램 사용 중 발생하는 모든 문제(데이터 손실, 손상 등)에 대한 책임은 사용자 본인에게 있습니다.\n- 본 프로그램은 한글과컴퓨터(주)와 무관하며, 정품 한글(Hancom Office) 설치가 필요합니다.',
        price=0.00,
        is_active=True,
        is_featured=False,
        is_guest_allowed=True,
        icon='📄',
        color_theme='blue',
        card_size='small',
        display_order=14,
        service_type='tool',
        external_url='https://drive.google.com/file/d/1JfFn1WtkJyMBQ0OUleXPQPTf2t9ecgyq/view?usp=sharing',
    )

    features = [
        {
            'icon': '⚡',
            'title': '빠른 변환',
            'description': '한글 OLE Automation을 활용한 고품질 PDF 변환',
        },
        {
            'icon': '🖥️',
            'title': '로컬 실행',
            'description': '서버 불필요, 단일 exe 파일로 바로 실행',
        },
        {
            'icon': '📂',
            'title': 'HWP/HWPX 지원',
            'description': 'HWP 및 HWPX 형식 모두 변환 가능',
        },
    ]

    for feature in features:
        ProductFeature.objects.create(product=product, **feature)

    print("[OK] HWP to PDF converter product created.")


def remove_hwp_converter(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    Product.objects.filter(title='HWP to PDF 변환기').delete()
    print("[OK] HWP to PDF converter product deleted.")


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0019_recreate_ssambti_product'),
    ]

    operations = [
        migrations.RunPython(add_hwp_converter, remove_hwp_converter),
    ]
