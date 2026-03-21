from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quickdrop", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="quickdropchannel",
            name="active_pair_issued_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="quickdropchannel",
            name="active_pair_nonce",
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
