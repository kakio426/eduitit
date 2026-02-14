from django.conf import settings
from django.db import models


class JanggiMatchLog(models.Model):
    MODE_CHOICES = [
        ('local', 'Local'),
        ('ai', 'AI'),
    ]
    RESULT_CHOICES = [
        ('red_win', 'Red Win'),
        ('blue_win', 'Blue Win'),
        ('draw', 'Draw'),
        ('in_progress', 'In Progress'),
    ]

    mode = models.CharField(max_length=12, choices=MODE_CHOICES, default='local')
    difficulty = models.CharField(max_length=16, blank=True)
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, default='in_progress')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='janggi_match_logs',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"JanggiMatchLog({self.mode}, {self.result})"

