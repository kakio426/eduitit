from django.db import migrations, models

import consent.models


class Migration(migrations.Migration):

    dependencies = [
        ("consent", "0003_alter_consent_filefields_storage"),
    ]

    operations = [
        migrations.AlterField(
            model_name="signaturedocument",
            name="original_file",
            field=models.FileField(
                storage=consent.models.get_document_storage,
                upload_to="signatures/consent/originals/%Y/%m/%d",
            ),
        ),
    ]
