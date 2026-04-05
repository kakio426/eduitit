from django.db import migrations


def _table_names(connection):
    with connection.cursor() as cursor:
        return set(connection.introspection.table_names(cursor))


def _column_names(connection, table_name):
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, table_name)
    return [column.name for column in description]


def repair_textbookmaterial_schema(apps, schema_editor):
    connection = schema_editor.connection
    table_name = "textbooks_textbookmaterial"
    if table_name not in _table_names(connection):
        return

    textbook_material = apps.get_model("textbooks", "TextbookMaterial")
    for field_name in ["source_type", "pdf_file", "page_count", "pdf_sha256", "original_filename"]:
        current_columns = set(_column_names(connection, table_name))
        if field_name not in current_columns:
            field = textbook_material._meta.get_field(field_name)
            schema_editor.add_field(textbook_material, field)

    current_columns = set(_column_names(connection, table_name))
    quote_name = connection.ops.quote_name
    quoted_table = quote_name(table_name)

    if "source_type" in current_columns:
        quoted_source_type = quote_name("source_type")
        if "pdf_file" in current_columns:
            quoted_pdf_file = quote_name("pdf_file")
            schema_editor.execute(
                f"UPDATE {quoted_table} SET {quoted_source_type} = 'pdf' "
                f"WHERE ({quoted_source_type} IS NULL OR TRIM({quoted_source_type}) = '') "
                f"AND {quoted_pdf_file} IS NOT NULL AND TRIM({quoted_pdf_file}) <> ''"
            )
        schema_editor.execute(
            f"UPDATE {quoted_table} SET {quoted_source_type} = 'markdown' "
            f"WHERE {quoted_source_type} IS NULL OR TRIM({quoted_source_type}) = ''"
        )

    for field_name, default_value in [("page_count", "0"), ("pdf_sha256", "''"), ("original_filename", "''")]:
        if field_name in current_columns:
            quoted_field = quote_name(field_name)
            schema_editor.execute(
                f"UPDATE {quoted_table} SET {quoted_field} = {default_value} WHERE {quoted_field} IS NULL"
            )


class Migration(migrations.Migration):
    dependencies = [
        ("textbooks", "0001_initial"),
        ("edu_materials", "0002_import_from_textbooks"),
    ]

    operations = [
        migrations.RunPython(repair_textbookmaterial_schema, migrations.RunPython.noop),
    ]
