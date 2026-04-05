from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0035_teacherbuddy_phase3"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="teacherbuddystate",
            name="active_skin_key",
            field=models.CharField(blank=True, default="", max_length=60),
        ),
        migrations.AddField(
            model_name="teacherbuddystate",
            name="profile_skin_key",
            field=models.CharField(blank=True, default="", max_length=60),
        ),
        migrations.CreateModel(
            name="TeacherBuddySkinUnlock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("skin_key", models.CharField(max_length=60)),
                ("buddy_key", models.CharField(max_length=60)),
                ("obtained_via", models.CharField(default="dust", max_length=24)),
                ("obtained_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="teacher_buddy_skin_unlocks", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-obtained_at", "id"],
                "constraints": [
                    models.UniqueConstraint(fields=("user", "skin_key"), name="uniq_teacher_buddy_skin_unlock"),
                ],
                "indexes": [
                    models.Index(fields=["user", "buddy_key"], name="core_tb_skin_user_buddy_idx"),
                    models.Index(fields=["user", "-obtained_at"], name="core_tb_skin_user_time_idx"),
                ],
            },
        ),
    ]
