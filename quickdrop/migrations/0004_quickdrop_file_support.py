from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quickdrop", "0003_quickdropitem"),
    ]

    operations = [
        migrations.AddField(
            model_name="quickdropitem",
            name="file",
            field=models.FileField(blank=True, null=True, upload_to="quickdrop/items/%Y/%m/"),
        ),
        migrations.AlterField(
            model_name="quickdropitem",
            name="kind",
            field=models.CharField(choices=[("text", "텍스트"), ("image", "이미지"), ("file", "파일")], max_length=20),
        ),
        migrations.AlterField(
            model_name="quickdropsession",
            name="current_kind",
            field=models.CharField(
                choices=[("empty", "비어 있음"), ("text", "텍스트"), ("image", "이미지"), ("file", "파일")],
                default="empty",
                max_length=20,
            ),
        ),
    ]
