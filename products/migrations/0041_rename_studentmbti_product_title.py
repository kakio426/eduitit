from django.db import migrations


OLD_TITLE = "우리반 캐릭터 친구 찾기"
NEW_TITLE = "우리반BTI"
ROUTE_NAME = "studentmbti:landing"


def forward(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    Product.objects.filter(title=OLD_TITLE).update(title=NEW_TITLE)
    Product.objects.filter(title=NEW_TITLE, launch_route_name="").update(launch_route_name=ROUTE_NAME)


def backward(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    Product.objects.filter(title=NEW_TITLE).update(title=OLD_TITLE)


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0040_update_consent_feature_title"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
