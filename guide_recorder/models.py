import os
import uuid

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


def guide_step_screenshot_upload_to(instance, filename):
    session_id = instance.session_id or 'unassigned'
    safe_name = os.path.basename(str(filename or '').strip()) or 'screenshot.jpg'
    return f'guide_recorder/sessions/{session_id}/steps/{safe_name}'


class GuideSession(models.Model):
    title = models.CharField(max_length=200)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='guide_sessions',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=False)
    share_token = models.CharField(max_length=64, unique=True, blank=True, null=True, default=None)
    step_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']
        verbose_name = '가이드 세션'
        verbose_name_plural = '가이드 세션들'

    def __str__(self):
        return self.title

    def get_or_create_share_token(self):
        if not self.share_token:
            self.share_token = uuid.uuid4().hex
            self.save(update_fields=['share_token'])
        return self.share_token


class GuideStep(models.Model):
    session = models.ForeignKey(
        GuideSession,
        on_delete=models.CASCADE,
        related_name='steps',
    )
    order = models.PositiveIntegerField()
    screenshot = models.ImageField(
        upload_to=guide_step_screenshot_upload_to,
        blank=True,
    )
    description = models.CharField(max_length=500, blank=True)
    click_x = models.FloatField(default=0.0)
    click_y = models.FloatField(default=0.0)
    element_metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']
        unique_together = [('session', 'order')]
        verbose_name = '가이드 스텝'
        verbose_name_plural = '가이드 스텝들'

    def __str__(self):
        return f'{self.session.title} — Step {self.order}'
