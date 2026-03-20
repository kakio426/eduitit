from django.db import migrations


PRODUCT_GUEST_ACCESS_FIXES = {
    "인포보드": {
        "launch_route_name": "infoboard:dashboard",
        "is_guest_allowed": False,
    },
    "교육 자료실": {
        "launch_route_name": "edu_materials:main",
        "is_guest_allowed": False,
    },
    "행복의 씨앗": {
        "launch_route_name": "happy_seed:landing",
        "is_guest_allowed": True,
    },
    "교과서 라이브 수업": {
        "launch_route_name": "textbooks:main",
        "is_guest_allowed": False,
    },
    "학교 예약 시스템": {
        "launch_route_name": "reservations:dashboard_landing",
        "is_guest_allowed": False,
    },
}


def forward(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    for title, values in PRODUCT_GUEST_ACCESS_FIXES.items():
        Product.objects.filter(title=title).update(**values)


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0058_sync_game_service_menu"),
    ]

    operations = [
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
