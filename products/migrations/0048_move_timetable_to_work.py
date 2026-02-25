from django.db import migrations


TARGET_TITLE = "전담 시간표·특별실 배치 도우미"
TARGET_ROUTE = "timetable:main"


def move_timetable_to_work(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    (
        Product.objects.filter(launch_route_name=TARGET_ROUTE, service_type="classroom")
        .update(service_type="work")
    )
    (
        Product.objects.filter(
            title=TARGET_TITLE,
            launch_route_name="",
            service_type="classroom",
        )
        .update(service_type="work")
    )


def rollback_timetable_to_classroom(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    (
        Product.objects.filter(launch_route_name=TARGET_ROUTE, service_type="work")
        .update(service_type="classroom")
    )
    (
        Product.objects.filter(
            title=TARGET_TITLE,
            launch_route_name="",
            service_type="work",
        )
        .update(service_type="classroom")
    )


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0047_normalize_internal_launch_metadata"),
    ]

    operations = [
        migrations.RunPython(move_timetable_to_work, rollback_timetable_to_classroom),
    ]
