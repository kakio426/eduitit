from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0034_teacherbuddy_phase2"),
    ]

    operations = [
        migrations.AddField(
            model_name="teacherbuddydailyprogress",
            name="home_ticket_awarded",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="teacherbuddysocialrewardlog",
            name="normalized_text",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="teacherbuddystate",
            name="last_sns_bonus_week_key",
            field=models.CharField(blank=True, default="", max_length=12),
        ),
        migrations.AddField(
            model_name="teacherbuddystate",
            name="sticker_dust",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
