from django.db import migrations


def forward(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    Product.objects.filter(title="행복의 씨앗", launch_route_name="").update(
        launch_route_name="happy_seed:landing"
    )


def backward(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    Product.objects.filter(
        title="행복의 씨앗",
        launch_route_name="happy_seed:landing",
    ).update(launch_route_name="")


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0038_backfill_launch_route_names"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
