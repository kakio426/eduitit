from django.db import migrations

def add_yut_product(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    Product.objects.create(
        title="🐎 온라인 윷놀이",
        description="학생들과 함께 즐길 수 있는 디지털 윷놀이 게임입니다. 별도의 설치 없이 브라우저에서 바로 실행 가능합니다.",
        price=0,
        is_active=True
    )

def remove_yut_product(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    Product.objects.filter(title="🐎 온라인 윷놀이").delete()

class Migration(migrations.Migration):

    dependencies = [
        ('products', '0003_userownedproduct'),
    ]

    operations = [
        migrations.RunPython(add_yut_product, remove_yut_product),
    ]
