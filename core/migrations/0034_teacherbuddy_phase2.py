import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def populate_teacher_buddy_share_tokens(apps, schema_editor):
    TeacherBuddyState = apps.get_model('core', 'TeacherBuddyState')
    for state in TeacherBuddyState.objects.filter(public_share_token__isnull=True):
        state.public_share_token = uuid.uuid4()
        state.save(update_fields=['public_share_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0033_teacherbuddydailyprogress_teacherbuddystate_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='teacherbuddydailyprogress',
            name='qualified_for_legendary_day',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='teacherbuddydailyprogress',
            name='sns_reward_awarded',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='teacherbuddydailyprogress',
            name='sns_reward_post_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='teacherbuddystate',
            name='profile_buddy_key',
            field=models.CharField(blank=True, default='', max_length=60),
        ),
        migrations.AddField(
            model_name='teacherbuddystate',
            name='public_share_token',
            field=models.UUIDField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='teacherbuddystate',
            name='qualifying_day_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name='TeacherBuddySocialRewardLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('post_id', models.PositiveIntegerField(blank=True, null=True)),
                ('activity_date', models.DateField()),
                ('content_hash', models.CharField(blank=True, default='', max_length=64)),
                ('reward_granted', models.BooleanField(default=False)),
                ('rejection_reason', models.CharField(blank=True, default='', max_length=40)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='teacher_buddy_social_reward_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': '교실 메이트 SNS 보상 로그',
                'verbose_name_plural': '교실 메이트 SNS 보상 로그',
                'indexes': [
                    models.Index(fields=['user', '-activity_date'], name='core_teache_user_id_8fb664_idx'),
                    models.Index(fields=['user', 'content_hash'], name='core_teache_user_id_869d3a_idx'),
                    models.Index(fields=['user', 'reward_granted'], name='core_teache_user_id_33c238_idx'),
                ],
            },
        ),
        migrations.RunPython(populate_teacher_buddy_share_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='teacherbuddystate',
            name='public_share_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
