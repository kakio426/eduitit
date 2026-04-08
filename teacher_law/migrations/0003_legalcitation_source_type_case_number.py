from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("teacher_law", "0002_seed_teacher_law_service"),
    ]

    operations = [
        migrations.AddField(
            model_name="legalcitation",
            name="case_number",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="legalcitation",
            name="source_type",
            field=models.CharField(
                choices=[("law", "법령"), ("case", "판례")],
                default="law",
                max_length=16,
            ),
        ),
    ]
