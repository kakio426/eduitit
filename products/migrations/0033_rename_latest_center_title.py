from django.db import migrations


OLD_TITLE = "최신본 센터"
NEW_TITLE = "최종최최종은 이제그만"


def forwards(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    Product.objects.filter(title=OLD_TITLE).update(title=NEW_TITLE)


def backwards(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    Product.objects.filter(title=NEW_TITLE).update(title=OLD_TITLE)


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0032_add_v2_home_fields"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

