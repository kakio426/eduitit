from django.db import migrations


def promote_review_banks_to_public(apps, schema_editor):
    SQQuizBank = apps.get_model("seed_quiz", "SQQuizBank")
    SQQuizBank.objects.filter(quality_status="review").update(
        quality_status="approved",
        is_public=True,
        share_opt_in=True,
    )


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ("seed_quiz", "0007_grade_choices"),
    ]

    operations = [
        migrations.RunPython(promote_review_banks_to_public, reverse_code=noop_reverse),
    ]

