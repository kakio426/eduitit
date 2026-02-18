from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0036_remove_padlet_and_school_violence_services"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="launch_route_name",
            field=models.CharField(
                blank=True,
                help_text="Internal Django URL name for direct launch (e.g. collect:landing).",
                max_length=120,
            ),
        ),
    ]
