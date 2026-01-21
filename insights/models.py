from django.db import models

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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    def get_video_id(self):
        """Extracts video ID from YouTube URL"""
        if "youtu.be" in self.video_url:
            return self.video_url.split("/")[-1]
        if "youtube.com" in self.video_url:
            import urllib.parse as urlparse
            query = urlparse.parse_qs(urlparse.urlparse(self.video_url).query)
            return query.get("v", [None])[0]
        return None

    def save(self, *args, **kwargs):
        if not self.thumbnail_url and self.video_url:
            vid_id = self.get_video_id()
            if vid_id:
                self.thumbnail_url = f"https://img.youtube.com/vi/{vid_id}/maxresdefault.jpg"
        super().save(*args, **kwargs)
