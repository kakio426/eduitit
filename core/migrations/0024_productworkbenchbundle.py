from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_userprofile_default_classroom'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductWorkbenchBundle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80)),
                ('product_ids', models.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('last_used_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='product_workbench_bundles', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': '작업대 조합',
                'verbose_name_plural': '작업대 조합',
                'ordering': ['-last_used_at', '-updated_at', 'name'],
            },
        ),
        migrations.AddIndex(
            model_name='productworkbenchbundle',
            index=models.Index(fields=['user', '-updated_at'], name='core_produc_user_id_5e220c_idx'),
        ),
        migrations.AddIndex(
            model_name='productworkbenchbundle',
            index=models.Index(fields=['user', '-last_used_at'], name='core_produc_user_id_f8fddb_idx'),
        ),
        migrations.AddConstraint(
            model_name='productworkbenchbundle',
            constraint=models.UniqueConstraint(fields=('user', 'name'), name='core_workbenchbundle_user_name_unique'),
        ),
    ]
