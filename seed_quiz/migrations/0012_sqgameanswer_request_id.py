import uuid

from django.db import migrations, models


def populate_sqgameanswer_request_ids(apps, schema_editor):
    SQGameAnswer = apps.get_model("seed_quiz", "SQGameAnswer")
    for answer in SQGameAnswer.objects.filter(request_id__isnull=True).iterator():
        answer.request_id = uuid.uuid4()
        answer.save(update_fields=["request_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("seed_quiz", "0011_sqgamequestion_request_id_and_needs_review"),
    ]

    operations = [
        migrations.AddField(
            model_name="sqgameanswer",
            name="request_id",
            field=models.UUIDField(blank=True, null=True, verbose_name="답안 요청 ID"),
        ),
        migrations.RunPython(populate_sqgameanswer_request_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="sqgameanswer",
            name="request_id",
            field=models.UUIDField(default=uuid.uuid4, unique=True, verbose_name="답안 요청 ID"),
        ),
    ]
