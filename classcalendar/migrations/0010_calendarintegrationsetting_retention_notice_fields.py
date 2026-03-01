from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("classcalendar", "0009_calendarcollaborator"),
    ]

    operations = [
        migrations.AddField(
            model_name="calendarintegrationsetting",
            name="retention_notice_banner_dismissed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="calendarintegrationsetting",
            name="retention_notice_event_seeded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
