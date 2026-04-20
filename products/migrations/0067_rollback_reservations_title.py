from django.db import migrations


def rollback_reservations_title(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ServiceManual = apps.get_model("products", "ServiceManual")

    route_name = "reservations:dashboard_landing"
    old_title = "학교 예약 시스템"
    new_title = "잇티예약"

    Product.objects.filter(launch_route_name=route_name).update(title=old_title)
    ServiceManual.objects.filter(product__launch_route_name=route_name).update(
        title=f"{old_title} 사용 가이드"
    )
    ServiceManual.objects.filter(
        product__launch_route_name=route_name,
        title=f"{new_title} 사용 가이드",
    ).update(title=f"{old_title} 사용 가이드")


def reapply_reservations_title(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ServiceManual = apps.get_model("products", "ServiceManual")

    route_name = "reservations:dashboard_landing"
    old_title = "학교 예약 시스템"
    new_title = "잇티예약"

    Product.objects.filter(launch_route_name=route_name).update(title=new_title)
    ServiceManual.objects.filter(product__launch_route_name=route_name).update(
        title=f"{new_title} 사용 가이드"
    )
    ServiceManual.objects.filter(
        product__launch_route_name=route_name,
        title=f"{old_title} 사용 가이드",
    ).update(title=f"{new_title} 사용 가이드")


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0066_rename_itit_service_titles"),
    ]

    operations = [
        migrations.RunPython(rollback_reservations_title, reapply_reservations_title),
    ]
