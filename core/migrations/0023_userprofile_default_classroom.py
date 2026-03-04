from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("happy_seed", "0004_alter_hsclasseventlog_type"),
        ("core", "0022_post_featured_window"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="default_classroom",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="default_users",
                to="happy_seed.hsclassroom",
                verbose_name="기본 학급",
            ),
        ),
    ]
