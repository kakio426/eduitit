import secrets

from django.db import migrations


def _generate_unique_token(SignatureRequest):
    while True:
        token = secrets.token_urlsafe(24)
        if not SignatureRequest.objects.filter(shared_lookup_token=token).exists():
            return token


def backfill_shared_lookup_tokens(apps, schema_editor):
    SignatureRequest = apps.get_model("consent", "SignatureRequest")
    for consent_request in SignatureRequest.objects.filter(shared_lookup_token__isnull=True).iterator():
        consent_request.shared_lookup_token = _generate_unique_token(SignatureRequest)
        consent_request.save(update_fields=["shared_lookup_token"])


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("consent", "0009_signaturerequest_shared_lookup_token"),
    ]

    operations = [
        migrations.RunPython(backfill_shared_lookup_tokens, noop_reverse),
    ]
