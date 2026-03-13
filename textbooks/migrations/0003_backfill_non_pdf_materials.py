from django.db import migrations


VALID_SUBJECTS = {"KOREAN", "MATH", "SOCIAL", "SCIENCE", "OTHER"}


def _normalized_subject(value):
    if value in VALID_SUBJECTS:
        return value
    return "OTHER"


def _matching_material_exists(edu_material_model, textbook_material):
    return edu_material_model.objects.filter(
        teacher_id=textbook_material.teacher_id,
        subject=_normalized_subject(getattr(textbook_material, "subject", None)),
        grade=(getattr(textbook_material, "grade", "") or ""),
        unit_title=(getattr(textbook_material, "unit_title", "") or ""),
        title=(getattr(textbook_material, "title", "") or "이관된 교육 자료"),
        html_content=(getattr(textbook_material, "content", "") or ""),
        original_filename=(getattr(textbook_material, "original_filename", "") or ""),
        created_at=getattr(textbook_material, "created_at", None),
        updated_at=getattr(textbook_material, "updated_at", None),
    ).exists()


def backfill_non_pdf_textbook_rows(textbook_material_model, edu_material_model):
    created = 0
    queryset = (
        textbook_material_model.objects.exclude(source_type="pdf")
        .order_by("created_at", "pk")
    )

    for textbook_material in queryset.iterator():
        if _matching_material_exists(edu_material_model, textbook_material):
            continue

        edu_material = edu_material_model.objects.create(
            teacher_id=textbook_material.teacher_id,
            subject=_normalized_subject(getattr(textbook_material, "subject", None)),
            grade=(getattr(textbook_material, "grade", "") or ""),
            unit_title=(getattr(textbook_material, "unit_title", "") or ""),
            title=(getattr(textbook_material, "title", "") or "이관된 교육 자료"),
            html_content=(getattr(textbook_material, "content", "") or ""),
            input_mode="file" if (getattr(textbook_material, "original_filename", "") or "").strip() else "paste",
            original_filename=(getattr(textbook_material, "original_filename", "") or ""),
            is_published=bool(getattr(textbook_material, "is_published", False)),
            view_count=0,
        )

        timestamp_updates = {}
        if getattr(textbook_material, "created_at", None) is not None:
            timestamp_updates["created_at"] = textbook_material.created_at
        if getattr(textbook_material, "updated_at", None) is not None:
            timestamp_updates["updated_at"] = textbook_material.updated_at
        if timestamp_updates:
            edu_material_model.objects.filter(pk=edu_material.pk).update(**timestamp_updates)
        created += 1

    return created


def forwards(apps, schema_editor):
    textbook_material_model = apps.get_model("textbooks", "TextbookMaterial")
    edu_material_model = apps.get_model("edu_materials", "EduMaterial")
    backfill_non_pdf_textbook_rows(textbook_material_model, edu_material_model)


class Migration(migrations.Migration):
    dependencies = [
        ("edu_materials", "0003_alter_edumaterial_grade_and_more"),
        ("textbooks", "0002_repair_legacy_schema"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
