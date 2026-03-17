from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("classcalendar", "0016_remove_retention_notice"),
    ]

    operations = [
        migrations.AlterField(
            model_name="calendarmessagecapturecandidate",
            name="candidate_kind",
            field=models.CharField(
                choices=[
                    ("event", "Event"),
                    ("meeting", "Meeting"),
                    ("class", "Class"),
                    ("consulting", "Consulting"),
                    ("training", "Training"),
                    ("exam", "Exam"),
                    ("deadline", "Deadline"),
                    ("prep", "Prep"),
                ],
                default="event",
                max_length=20,
            ),
        ),
    ]
