from django.db import migrations

def add_dutyticker_product(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    ProductFeature = apps.get_model('products', 'ProductFeature')

    # DutyTicker 서비스 생성
    dutyticker_product = Product.objects.create(
        title="DutyTicker",
        description="교실 대형 화면을 위한 1인 1역 알리미 대시보드입니다. 오늘의 일정, 타이머, 방송 알림 기능을 한눈에 확인하세요.",
        price=0,
        is_active=True,
        is_featured=True,
        icon="fa-solid fa-chalkboard-user",
        color_theme="blue",
        card_size="wide",
        display_order=0,
        service_type="tool",
        external_url="",
    )

    # DutyTicker 기능 추가
    features = [
        {
            "icon": "fa-solid fa-user-check",
            "title": "1인 1역 현황 관리",
            "description": "학급의 1인 1역 수행 현황을 대화면에서 실시간으로 확인하고 관리할 수 있습니다.",
        },
        {
            "icon": "fa-solid fa-bullhorn",
            "title": "전체 방송 알림",
            "description": "선생님이 전달하고 싶은 메시지를 시각적인 효과와 알림음으로 학생들에게 즉시 알립니다.",
        },
        {
            "icon": "fa-solid fa-stopwatch",
            "title": "맞춤형 집중 타이머",
            "description": "수업 시간, 쉬는 시간, 집중 시간 등 상황에 맞는 타이머를 간편하게 설정하고 사용합니다.",
        },
    ]

    for feature in features:
        ProductFeature.objects.create(product=dutyticker_product, **feature)


def remove_dutyticker_product(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    Product.objects.filter(title="DutyTicker").delete()


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0010_add_saju_product'),
    ]

    operations = [
        migrations.RunPython(add_dutyticker_product, remove_dutyticker_product),
    ]
