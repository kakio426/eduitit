from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("consent", "0011_alter_signaturerequest_shared_lookup_token"),
    ]

    operations = [
        migrations.AlterField(
            model_name="consentauditlog",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("lookup_success", "Lookup Success"),
                    ("lookup_fail", "Lookup Fail"),
                    ("verify_success", "Verify Success"),
                    ("verify_fail", "Verify Fail"),
                    ("sign_submitted", "Sign Submitted"),
                    ("link_created", "Link Created"),
                    ("request_sent", "Request Sent"),
                    ("document_viewed", "Document Viewed"),
                ],
                max_length=40,
            ),
        ),
    ]
