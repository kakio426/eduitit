from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("edu_materials", "0004_edumaterial_material_type_edumaterial_metadata_confidence_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="edumaterial",
            name="is_published",
            field=models.BooleanField(default=False, verbose_name="공개 여부"),
        ),
    ]
