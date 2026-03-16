from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("consent", "0008_signaturerecipient_identity_assurance_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="signaturerequest",
            name="shared_lookup_token",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
    ]
