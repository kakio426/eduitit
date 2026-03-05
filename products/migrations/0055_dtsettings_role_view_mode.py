from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0054_update_reservations_icon"),
    ]

    operations = [
        migrations.AddField(
            model_name="dtsettings",
            name="role_view_mode",
            field=models.CharField(
                choices=[("compact", "밀도형 (기본)"), ("readable", "가독성형 (큰 글씨)")],
                default="compact",
                help_text="오늘의 역할 표시 모드",
                max_length=20,
            ),
        ),
    ]
