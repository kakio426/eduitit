from django.db import migrations, models


def copy_pinned_notice_state_to_profiles(apps, schema_editor):
    SiteConfig = apps.get_model('core', 'SiteConfig')
    UserProfile = apps.get_model('core', 'UserProfile')

    expanded = (
        SiteConfig.objects
        .filter(pk=1)
        .values_list('pinned_notice_expanded', flat=True)
        .first()
    )
    if expanded:
        UserProfile.objects.update(pinned_notice_expanded=True)


def copy_pinned_notice_state_to_site_config(apps, schema_editor):
    SiteConfig = apps.get_model('core', 'SiteConfig')
    UserProfile = apps.get_model('core', 'UserProfile')

    has_expanded_profile = UserProfile.objects.filter(pinned_notice_expanded=True).exists()
    config, _ = SiteConfig.objects.get_or_create(pk=1)
    config.pinned_notice_expanded = has_expanded_profile
    config.save(update_fields=['pinned_notice_expanded'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0027_rename_core_post_feature_8fcae1_idx_core_post_feature_433f55_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='pinned_notice_expanded',
            field=models.BooleanField(default=False, verbose_name='고정 공지 펼침 상태'),
        ),
        migrations.RunPython(
            copy_pinned_notice_state_to_profiles,
            reverse_code=copy_pinned_notice_state_to_site_config,
        ),
        migrations.RemoveField(
            model_name='siteconfig',
            name='pinned_notice_expanded',
        ),
    ]
