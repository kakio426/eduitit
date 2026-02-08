from django.db import migrations

def clear_fortune_data(apps, schema_editor):
    FortuneResult = apps.get_model('fortune', 'FortuneResult')
    DailyFortuneLog = apps.get_model('fortune', 'DailyFortuneLog')
    
    # Delete all records
    FortuneResult.objects.all().delete()
    DailyFortuneLog.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('fortune', '0007_alter_fortuneresult_topic'),
    ]

    operations = [
        migrations.RunPython(clear_fortune_data),
    ]
