from django.db import migrations

OLD_URL = 'https://drive.google.com/file/d/1JfFn1WtkJyMBQ0OUleXPQPTf2t9ecgyq/view?usp=sharing'
NEW_URL = 'https://drive.google.com/file/d/11FIEgxWXV2q8fWNPc5CaAXwEQPCNr4VI/view?usp=sharing'
PRODUCT_TITLE = 'HWP to PDF 변환기'


def forwards(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    Product.objects.filter(title=PRODUCT_TITLE).update(external_url=NEW_URL)


def backwards(apps, schema_editor):
    Product = apps.get_model('products', 'Product')
    Product.objects.filter(title=PRODUCT_TITLE).update(external_url=OLD_URL)


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0030_backfill_missing_service_manuals'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
