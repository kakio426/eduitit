from django.db import migrations


TARGET_TITLE = "별빛 추첨기"
TARGET_ROUTE = "ppobgi:main"


def move_ppobgi_to_classroom(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    (
        Product.objects.filter(launch_route_name=TARGET_ROUTE, service_type="game")
        .update(service_type="classroom")
    )
    (
        Product.objects.filter(
            title=TARGET_TITLE,
            launch_route_name="",
            service_type="game",
        )
        .update(service_type="classroom")
    )


def rollback_ppobgi_to_game(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    (
        Product.objects.filter(launch_route_name=TARGET_ROUTE, service_type="classroom")
        .update(service_type="game")
    )
    (
        Product.objects.filter(
            title=TARGET_TITLE,
            launch_route_name="",
            service_type="classroom",
        )
        .update(service_type="game")
    )


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0043_rename_hwpxchat_service_title"),
    ]

    operations = [
        migrations.RunPython(move_ppobgi_to_classroom, rollback_ppobgi_to_game),
    ]
