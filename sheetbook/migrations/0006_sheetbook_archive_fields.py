from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sheetbook", "0005_alter_actioninvocation_action_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="sheetbook",
            name="archived_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sheetbook",
            name="is_archived",
            field=models.BooleanField(default=False),
        ),
        migrations.AddIndex(
            model_name="sheetbook",
            index=models.Index(fields=["owner", "is_archived", "updated_at"], name="sheetbook_s_owner_i_ccd523_idx"),
        ),
    ]
