from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0004_achievementphoto"),
    ]

    operations = [
        migrations.AddField(
            model_name="achievement",
            name="image_caption",
            field=models.CharField(
                blank=True,
                help_text="포트폴리오 카드의 대표 이미지 아래에 바로 노출되는 짧은 설명입니다.",
                max_length=200,
                verbose_name="대표 이미지 설명",
            ),
        ),
    ]
