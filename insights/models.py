from django.db import models
from django.contrib.auth.models import User
from urllib.parse import parse_qs, urlparse

from .text_formatting import auto_format_insight_text

class Insight(models.Model):
    CATEGORY_CHOICES = [
        ('youtube', 'YouTube Scrap'),
        ('devlog', 'DevLog (Development Log)'),
        ('column', 'Column/Essay'),
    ]

    title = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='youtube', verbose_name="카테고리")
    video_url = models.URLField(help_text="YouTube video URL", blank=True, null=True)
    thumbnail_url = models.URLField(blank=True, help_text="Auto-generated or custom thumbnail URL")
    content = models.TextField(help_text="Main insight or quote")
    kakio_note = models.TextField(blank=True, help_text="Teacher's special note")
    tags = models.CharField(max_length=100, help_text="Comma-separated tags e.g. #Leadership", blank=True)
    is_featured = models.BooleanField(default=False)
    likes = models.ManyToManyField(User, related_name='liked_insights', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    @property
    def total_likes(self):
        return self.likes.count()

    def get_video_id(self):
        """Extract a YouTube video ID from common URL formats."""
        if not self.video_url:
            return None

        parsed = urlparse(self.video_url.strip())
        host = parsed.netloc.lower()
        path_parts = [part for part in parsed.path.split("/") if part]

        if "youtu.be" in host:
            return path_parts[0] if path_parts else None

        if "youtube.com" not in host and "youtube-nocookie.com" not in host:
            return None

        query_video_id = parse_qs(parsed.query).get("v", [None])[0]
        if query_video_id:
            return query_video_id

        if path_parts and path_parts[0] in {"shorts", "embed", "live", "v"}:
            return path_parts[1] if len(path_parts) >= 2 else None

        return None

    def save(self, *args, **kwargs):
        self.content = auto_format_insight_text(self.content)
        if self.kakio_note:
            self.kakio_note = auto_format_insight_text(self.kakio_note)

        if not self.thumbnail_url and self.video_url:
            vid_id = self.get_video_id()
            if vid_id:
                self.thumbnail_url = f"https://img.youtube.com/vi/{vid_id}/maxresdefault.jpg"
        super().save(*args, **kwargs)
