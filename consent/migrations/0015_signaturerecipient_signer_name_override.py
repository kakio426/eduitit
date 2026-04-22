from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("consent", "0014_signatureposition_check_rule_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="signaturerecipient",
            name="signer_name_override",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
