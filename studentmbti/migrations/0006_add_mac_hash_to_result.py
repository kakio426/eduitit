from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('studentmbti', '0005_testsession_test_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentmbtiresult',
            name='mac_hash',
            field=models.CharField(
                max_length=64,
                blank=True,
                null=True,
                db_index=True,
                help_text='Device hash',
            ),
        ),
    ]
