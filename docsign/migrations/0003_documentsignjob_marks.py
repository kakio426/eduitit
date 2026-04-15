from django.db import migrations, models


def forwards(apps, schema_editor):
    DocumentSignJob = apps.get_model("docsign", "DocumentSignJob")
    for job in DocumentSignJob.objects.all().iterator():
        if getattr(job, "marks", None):
            continue
        if all(
            value is not None
            for value in (job.signature_page, job.x, job.y, job.width, job.height)
        ):
            job.marks = [
                {
                    "page": int(job.signature_page),
                    "x": float(job.x),
                    "y": float(job.y),
                    "width": float(job.width),
                    "height": float(job.height),
                    "mark_type": (job.mark_type or "signature"),
                }
            ]
            job.save(update_fields=["marks"])


def backwards(apps, schema_editor):
    DocumentSignJob = apps.get_model("docsign", "DocumentSignJob")
    for job in DocumentSignJob.objects.all().iterator():
        job.marks = []
        job.save(update_fields=["marks"])


class Migration(migrations.Migration):
    dependencies = [
        ("docsign", "0002_documentsignjob_mark_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="documentsignjob",
            name="marks",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(forwards, backwards),
    ]
