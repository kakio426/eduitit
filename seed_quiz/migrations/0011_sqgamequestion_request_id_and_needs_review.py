import uuid

from django.db import migrations, models


def populate_sqgamequestion_request_ids(apps, schema_editor):
    SQGameQuestion = apps.get_model("seed_quiz", "SQGameQuestion")
    for question in SQGameQuestion.objects.filter(request_id__isnull=True).iterator():
        question.request_id = uuid.uuid4()
        question.save(update_fields=["request_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("seed_quiz", "0010_sqgameplayer_sqgameroom_sqgamereward_sqgamequestion_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="sqgamequestion",
            name="request_id",
            field=models.UUIDField(blank=True, null=True, verbose_name="제출 요청 ID"),
        ),
        migrations.RunPython(populate_sqgamequestion_request_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="sqgamequestion",
            name="request_id",
            field=models.UUIDField(default=uuid.uuid4, unique=True, verbose_name="제출 요청 ID"),
        ),
        migrations.AlterField(
            model_name="sqgamequestion",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "작성중"),
                    ("pending_ai", "AI 평가중"),
                    ("needs_review", "교사 확인 필요"),
                    ("ready", "사용 가능"),
                    ("rejected", "제외"),
                ],
                default="draft",
                max_length=12,
                verbose_name="상태",
            ),
        ),
    ]
