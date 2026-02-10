from django.db import models
from django.contrib.auth.models import User


class NotebookEntry(models.Model):
    """NotebookLM 링크 게시판 항목"""
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notebook_entries')
    title = models.CharField(max_length=200, verbose_name='제목')
    description = models.TextField(blank=True, verbose_name='설명')
    notebook_url = models.URLField(verbose_name='NotebookLM 링크')
    is_active = models.BooleanField(default=True, verbose_name='공개')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'NotebookLM 항목'
        verbose_name_plural = 'NotebookLM 항목'

    def __str__(self):
        return self.title
