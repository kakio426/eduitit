from django.db import migrations


def add_saju_product(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    ProductFeature = apps.get_model('products', 'ProductFeature')

    # 사주 서비스 생성
    saju_product = Product.objects.create(
        title="사주 운세",
        description="생년월일을 기반으로 AI가 분석하는 사주 운세 서비스입니다. 오늘의 운세, 연애운, 재물운 등 다양한 분석을 제공합니다.",
        price=0,
        is_active=True,
        is_featured=False,
        icon="fa-solid fa-yin-yang",
        color_theme="purple",
        card_size="small",
        display_order=5,
        service_type="tool",
        external_url="/fortune/saju/",
    )

    # 사주 서비스 기능 추가
    features = [
        {
            "icon": "fa-solid fa-calendar-days",
            "title": "생년월일 기반 분석",
            "description": "정확한 생년월일과 시간을 입력하면 사주팔자를 기반으로 운세를 분석합니다.",
        },
        {
            "icon": "fa-solid fa-robot",
            "title": "AI 맞춤 해석",
            "description": "Gemini AI가 개인 맞춤형으로 운세를 해석하여 더욱 상세한 분석을 제공합니다.",
        },
        {
            "icon": "fa-solid fa-heart",
            "title": "다양한 운세 모드",
            "description": "종합 운세, 연애운, 재물운, 건강운 등 원하는 분야별 운세를 확인할 수 있습니다.",
        },
    ]

    for feature in features:
        ProductFeature.objects.create(product=saju_product, **feature)


def remove_saju_product(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    Product.objects.filter(title="사주 운세").delete()


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0009_update_prompt_recipe_size'),
    ]

    operations = [
        migrations.RunPython(add_saju_product, remove_saju_product),
    ]
