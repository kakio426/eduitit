from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('fortune', '0011_alter_favoritedate_profile_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='dailyfortunelog',
            name='profile',
        ),
        migrations.RemoveField(
            model_name='favoritedate',
            name='profile',
        ),
        migrations.RemoveField(
            model_name='fortuneresult',
            name='natal_chart',
        ),
        migrations.DeleteModel(
            name='ChatMessage',
        ),
        migrations.DeleteModel(
            name='ChatSession',
        ),
        migrations.DeleteModel(
            name='NatalChart',
        ),
        migrations.DeleteModel(
            name='SajuProfile',
        ),
        migrations.DeleteModel(
            name='UserSajuProfile',
        ),
    ]
