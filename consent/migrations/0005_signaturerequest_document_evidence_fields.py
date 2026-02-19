from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("consent", "0004_alter_signaturedocument_original_file_storage"),
    ]

    operations = [
        migrations.AddField(
            model_name="signaturerequest",
            name="document_name_snapshot",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="signaturerequest",
            name="document_sha256_snapshot",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="signaturerequest",
            name="document_size_snapshot",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
    ]
