from django.db import migrations
from django.db.models import Q


LEGACY_APP_LABEL = "".join(("sheet", "book"))
RETIRED_PRODUCT_TITLES = ("교무수첩", "학급 기록 보드")
LEGACY_ROUTE_PREFIX = f"{LEGACY_APP_LABEL}:"
LEGACY_TABLES = tuple(
    f"{LEGACY_APP_LABEL}_{suffix}"
    for suffix in (
        "sheetcell",
        "sheetcolumn",
        "sheetrow",
        "savedview",
        "actioninvocation",
        "".join(("sheet", "book", "metricevent")),
        "sheettab",
        "".join(("sheet", "book")),
    )
)


def purge_legacy_workspace_service(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ContentType = apps.get_model("contenttypes", "ContentType")

    Product.objects.filter(
        Q(launch_route_name__istartswith=LEGACY_ROUTE_PREFIX)
        | Q(title__in=RETIRED_PRODUCT_TITLES)
    ).delete()
    ContentType.objects.filter(app_label=LEGACY_APP_LABEL).delete()

    connection = schema_editor.connection
    existing_tables = set(connection.introspection.table_names())
    vendor = connection.vendor

    with connection.cursor() as cursor:
        for table_name in LEGACY_TABLES:
            if table_name not in existing_tables:
                continue
            quoted_table = schema_editor.quote_name(table_name)
            drop_sql = f"DROP TABLE IF EXISTS {quoted_table}"
            if vendor == "postgresql":
                drop_sql = f"{drop_sql} CASCADE"
            cursor.execute(drop_sql)


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("products", "0064_dttimeslot_morning_dtmissionautomation_slot_code"),
    ]

    operations = [
        migrations.RunPython(purge_legacy_workspace_service, migrations.RunPython.noop),
    ]
