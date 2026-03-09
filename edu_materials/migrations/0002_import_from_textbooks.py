from datetime import datetime

from django.db import migrations
from django.utils import timezone

VALID_SUBJECTS = {"KOREAN", "MATH", "SOCIAL", "SCIENCE", "OTHER"}


def _table_names(connection):
    with connection.cursor() as cursor:
        return set(connection.introspection.table_names(cursor))


def _column_names(connection, table_name):
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, table_name)
    return [column.name for column in description]


def _normalize_timestamp(value):
    if value in (None, ""):
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    if isinstance(value, datetime) and timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


def migrate_legacy_rows(schema_editor, edu_material_model, source_table="textbooks_textbookmaterial"):
    connection = schema_editor.connection
    if source_table not in _table_names(connection):
        return 0

    columns = _column_names(connection, source_table)
    column_set = set(columns)
    required = {"teacher_id", "subject", "grade", "unit_title", "title", "content"}
    if not required.issubset(column_set):
        return 0

    selected = ["teacher_id", "subject", "grade", "unit_title", "title", "content"]
    for optional in ["is_published", "created_at", "updated_at", "view_count", "is_shared", "source_type", "original_filename", "pdf_file"]:
        if optional in column_set:
            selected.append(optional)

    quote_name = connection.ops.quote_name
    query = f"SELECT {', '.join(quote_name(column) for column in selected)} FROM {quote_name(source_table)}"
    with connection.cursor() as cursor:
        cursor.execute(query)
        rows = [dict(zip(selected, row)) for row in cursor.fetchall()]

    created = 0
    for row in rows:
        source_type = str(row.get("source_type") or "").strip().lower()
        pdf_file = str(row.get("pdf_file") or "").strip()
        if "source_type" in column_set and (source_type == "pdf" or (not source_type and pdf_file)):
            continue

        subject = row.get("subject") or "OTHER"
        if subject not in VALID_SUBJECTS:
            subject = "OTHER"

        material = edu_material_model.objects.create(
            teacher_id=row["teacher_id"],
            subject=subject,
            grade=row.get("grade") or "",
            unit_title=row.get("unit_title") or "이관 자료",
            title=row.get("title") or "이관된 교육 자료",
            html_content=row.get("content") or "",
            input_mode="file" if str(row.get("original_filename") or "").strip() else "paste",
            original_filename=str(row.get("original_filename") or "").strip(),
            is_published=bool(row.get("is_published")) or bool(row.get("is_shared")),
            view_count=int(row.get("view_count") or 0),
        )
        timestamp_updates = {}
        created_at = _normalize_timestamp(row.get("created_at"))
        updated_at = _normalize_timestamp(row.get("updated_at"))
        if created_at:
            timestamp_updates["created_at"] = created_at
        if updated_at:
            timestamp_updates["updated_at"] = updated_at
        if timestamp_updates:
            edu_material_model.objects.filter(pk=material.pk).update(**timestamp_updates)
        created += 1

    return created


def import_legacy_textbook_rows(apps, schema_editor):
    edu_material_model = apps.get_model("edu_materials", "EduMaterial")
    migrate_legacy_rows(schema_editor, edu_material_model)


class Migration(migrations.Migration):
    dependencies = [
        ("edu_materials", "0001_initial"),
        ("textbooks", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(import_legacy_textbook_rows, migrations.RunPython.noop),
    ]
