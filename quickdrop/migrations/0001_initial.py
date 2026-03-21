import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="QuickdropChannel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.CharField(db_index=True, max_length=32, unique=True)),
                ("title", models.CharField(default="바로전송", max_length=80)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner",
                    models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="quickdrop_channel", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="QuickdropSession",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("live", "진행 중"), ("ended", "종료")], default="live", max_length=20)),
                ("current_kind", models.CharField(choices=[("empty", "비어 있음"), ("text", "텍스트"), ("image", "이미지")], default="empty", max_length=20)),
                ("current_text", models.TextField(blank=True)),
                ("current_image", models.ImageField(blank=True, null=True, upload_to="quickdrop/%Y/%m/")),
                ("current_mime_type", models.CharField(blank=True, max_length=100)),
                ("current_filename", models.CharField(blank=True, max_length=255)),
                ("last_activity_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "channel",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sessions", to="quickdrop.quickdropchannel"),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="QuickdropDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("device_id", models.CharField(max_length=64)),
                ("label", models.CharField(max_length=80)),
                ("paired_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("user_agent_summary", models.CharField(blank=True, max_length=120)),
                (
                    "channel",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="devices", to="quickdrop.quickdropchannel"),
                ),
            ],
            options={
                "ordering": ["paired_at"],
                "unique_together": {("channel", "device_id")},
            },
        ),
    ]
