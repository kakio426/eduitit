import random
import string

from django.db import migrations, models


def populate_access_codes(apps, schema_editor):
    EduMaterial = apps.get_model("edu_materials", "EduMaterial")
    existing_codes = set(
        EduMaterial.objects.exclude(access_code__isnull=True)
        .exclude(access_code="")
        .values_list("access_code", flat=True)
    )

    def generate_code():
        for _ in range(200):
            code = "".join(random.choices(string.digits, k=6))
            if code not in existing_codes:
                existing_codes.add(code)
                return code
        raise RuntimeError("학생 공유 코드를 생성하지 못했습니다.")

    pending = EduMaterial.objects.filter(
        models.Q(access_code__isnull=True) | models.Q(access_code="")
    )
    for material in pending.iterator():
        material.access_code = generate_code()
        material.save(update_fields=["access_code"])


class Migration(migrations.Migration):

    dependencies = [
        ("edu_materials", "0005_alter_edumaterial_is_published"),
    ]

    operations = [
        migrations.AddField(
            model_name="edumaterial",
            name="access_code",
            field=models.CharField(
                blank=True,
                help_text="학생 공유 코드",
                max_length=6,
                null=True,
                unique=True,
            ),
        ),
        migrations.RunPython(populate_access_codes, migrations.RunPython.noop),
    ]
