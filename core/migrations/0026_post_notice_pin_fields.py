from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0025_userpolicyconsent_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="allow_notice_dismiss",
            field=models.BooleanField(default=False, verbose_name="공지 닫기 허용"),
        ),
        migrations.AddField(
            model_name="post",
            name="is_notice_pinned",
            field=models.BooleanField(default=False, verbose_name="공지 상단 고정"),
        ),
    ]
