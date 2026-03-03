from django.db import migrations


def forwards(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    Product.objects.filter(title="학교 예약 시스템").update(icon="🏫")


def backwards(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    Product.objects.filter(title="학교 예약 시스템").update(icon="📅")


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0053_dtsettings_theme_alter_product_solve_text"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
