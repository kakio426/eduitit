from django.db import migrations, models


def publish_all_materials(apps, schema_editor):
    EduMaterial = apps.get_model("edu_materials", "EduMaterial")
    EduMaterial.objects.filter(is_published=False).update(is_published=True)


class Migration(migrations.Migration):

    dependencies = [
        ("edu_materials", "0006_edumaterial_access_code"),
    ]

    operations = [
        migrations.AlterField(
            model_name="edumaterial",
            name="is_published",
            field=models.BooleanField(default=True, verbose_name="공개 여부"),
        ),
        migrations.RunPython(publish_all_materials, migrations.RunPython.noop),
    ]
