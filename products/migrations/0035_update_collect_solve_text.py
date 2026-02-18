from django.db import migrations

def update_collect_solve_text(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    Product.objects.filter(title='간편 수합').update(
        solve_text='문서와 의견 수합, 번거로운 일은 이제 저에게 맡겨주세요!'
    )

class Migration(migrations.Migration):
    dependencies = [
        ('products', '0034_add_parent_consent_product'),
    ]

    operations = [
        migrations.RunPython(update_collect_solve_text),
    ]
