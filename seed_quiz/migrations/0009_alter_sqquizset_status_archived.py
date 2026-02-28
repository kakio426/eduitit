from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("seed_quiz", "0008_auto_share_review_banks"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sqquizset",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "초안"),
                    ("published", "배포중"),
                    ("closed", "종료"),
                    ("archived", "보관"),
                    ("failed", "생성실패"),
                ],
                default="draft",
                max_length=10,
                verbose_name="상태",
            ),
        ),
    ]
