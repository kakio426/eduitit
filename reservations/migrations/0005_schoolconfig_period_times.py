from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reservations', '0004_schoolconfig_weekly_opening_hour_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='schoolconfig',
            name='period_times',
            field=models.TextField(blank=True, default=''),
        ),
    ]

