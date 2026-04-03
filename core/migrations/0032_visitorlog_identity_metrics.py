from django.conf import settings
from django.db import migrations, models


def backfill_visitor_identity(apps, schema_editor):
    VisitorLog = apps.get_model("core", "VisitorLog")
    db_alias = schema_editor.connection.alias

    for log in VisitorLog.objects.using(db_alias).all().iterator():
        ip_address = log.ip_address or "0.0.0.0"
        identity_type = "bot" if log.is_bot else "ip"
        visitor_key = f"legacy-ip:{ip_address}"
        VisitorLog.objects.using(db_alias).filter(pk=log.pk).update(
            identity_type=identity_type,
            visitor_key=visitor_key,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0031_userprofile_recent_reservation_school_ids"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="visitorlog",
            name="identity_type",
            field=models.CharField(
                choices=[
                    ("user", "로그인 사용자"),
                    ("session", "브라우저 세션"),
                    ("bot", "봇"),
                    ("ip", "기존 IP"),
                ],
                default="session",
                max_length=20,
                verbose_name="식별 기준",
            ),
        ),
        migrations.AddField(
            model_name="visitorlog",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="visitor_logs",
                to=settings.AUTH_USER_MODEL,
                verbose_name="사용자",
            ),
        ),
        migrations.AddField(
            model_name="visitorlog",
            name="visitor_key",
            field=models.CharField(
                blank=True,
                db_index=True,
                max_length=80,
                null=True,
                verbose_name="방문 식별자",
            ),
        ),
        migrations.AlterField(
            model_name="visitorlog",
            name="visit_date",
            field=models.DateField(auto_now_add=True, db_index=True, verbose_name="방문 날짜"),
        ),
        migrations.RunPython(backfill_visitor_identity, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="visitorlog",
            name="visitor_key",
            field=models.CharField(db_index=True, max_length=80, verbose_name="방문 식별자"),
        ),
        migrations.AlterUniqueTogether(
            name="visitorlog",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="visitorlog",
            constraint=models.UniqueConstraint(
                fields=("visit_date", "visitor_key"),
                name="core_unique_visitor_per_day",
            ),
        ),
        migrations.AddIndex(
            model_name="visitorlog",
            index=models.Index(fields=["visit_date", "is_bot"], name="core_visito_visit_d_1c7ec6_idx"),
        ),
    ]
