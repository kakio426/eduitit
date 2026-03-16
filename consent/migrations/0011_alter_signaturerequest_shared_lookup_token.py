from django.db import migrations, models

import consent.models


class Migration(migrations.Migration):

    dependencies = [
        ("consent", "0010_backfill_shared_lookup_tokens"),
    ]

    operations = [
        migrations.AlterField(
            model_name="signaturerequest",
            name="shared_lookup_token",
            field=models.CharField(
                default=consent.models._generate_shared_lookup_token,
                max_length=64,
                unique=True,
            ),
        ),
    ]
