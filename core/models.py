from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('school', '학교 (관리자 및 정교사)'),
        ('instructor', '강사 (기간제, 돌봄, 늘봄 등)'),
        ('company', '교육행사업체'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True, null=True, verbose_name="역할")
    gemini_api_key = models.CharField(max_length=255, blank=True, null=True, verbose_name="Gemini API Key")

    def __str__(self):
        return self.user.username

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    # Retrieve the profile to trigger creation if it doesn't exist (e.g. for existing users)
    # However, create_user_profile handles 'created'.
    # If the profile doesn't exist, we should probably create it.
    if not hasattr(instance, 'userprofile'):
        UserProfile.objects.create(user=instance)
    else:
        instance.userprofile.save()
