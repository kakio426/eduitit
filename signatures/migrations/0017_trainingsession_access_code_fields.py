from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("signatures", "0016_expectedparticipant_manual_sort_order_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="trainingsession",
            name="access_code_duration_minutes",
            field=models.PositiveSmallIntegerField(
                choices=[(0, "사용 안 함"), (5, "5분"), (10, "10분")],
                default=0,
                help_text="필요할 때만 5분 또는 10분짜리 현장 코드를 걸 수 있습니다.",
                verbose_name="현장 코드 유효 시간",
            ),
        ),
        migrations.AddField(
            model_name="trainingsession",
            name="active_access_code",
            field=models.CharField(blank=True, max_length=6, verbose_name="현재 현장 코드"),
        ),
        migrations.AddField(
            model_name="trainingsession",
            name="active_access_code_expires_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="현재 현장 코드 만료 시각"),
        ),
    ]
