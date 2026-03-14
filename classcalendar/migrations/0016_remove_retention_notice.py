from django.db import migrations


RETENTION_NOTICE_TITLE = "[안내] 자동 정리 정책 안내"


def delete_retention_notice_events(apps, schema_editor):
    CalendarEvent = apps.get_model("classcalendar", "CalendarEvent")
    CalendarEvent.objects.filter(
        title=RETENTION_NOTICE_TITLE,
        source="local",
        is_locked=False,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("classcalendar", "0015_calendarmessagecapture_follow_up_state_and_more"),
    ]

    operations = [
        migrations.RunPython(delete_retention_notice_events, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="calendarintegrationsetting",
            name="retention_notice_banner_dismissed_at",
        ),
        migrations.RemoveField(
            model_name="calendarintegrationsetting",
            name="retention_notice_event_seeded_at",
        ),
    ]
