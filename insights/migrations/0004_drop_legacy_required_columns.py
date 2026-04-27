from django.db import migrations


LEGACY_COLUMNS = ("deck", "series_name", "track")


def drop_legacy_columns(apps, schema_editor):
    table_name = "insights_insight"
    connection = schema_editor.connection

    with connection.cursor() as cursor:
        if table_name not in connection.introspection.table_names(cursor):
            return

        existing_columns = {
            column.name
            for column in connection.introspection.get_table_description(cursor, table_name)
        }

    quoted_table = schema_editor.quote_name(table_name)
    for column_name in LEGACY_COLUMNS:
        if column_name not in existing_columns:
            continue
        schema_editor.execute(
            f"ALTER TABLE {quoted_table} DROP COLUMN {schema_editor.quote_name(column_name)}"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("insights", "0003_insight_likes"),
    ]

    operations = [
        migrations.RunPython(drop_legacy_columns, migrations.RunPython.noop),
    ]
