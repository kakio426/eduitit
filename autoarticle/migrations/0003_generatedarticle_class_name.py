from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("autoarticle", "0002_generatedarticle_event_date_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="generatedarticle",
            name="class_name",
            field=models.CharField(blank=True, max_length=50, verbose_name="참여 반"),
        ),
    ]
