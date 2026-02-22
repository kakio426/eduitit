from django.db import models
from django.contrib.auth.models import User


class TimetableSyncLog(models.Model):
    SYNC_MODE_CHOICES = [
        ("direct", "바로반영"),
        ("preview_manual", "미리보기 수동반영"),
    ]

    STATUS_CHOICES = [
        ("success", "성공"),
        ("partial", "부분반영"),
        ("skipped", "건너뜀"),
        ("failed", "실패"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="timetable_sync_logs",
        verbose_name="실행 사용자",
    )
    school_slug = models.CharField(max_length=120, verbose_name="학교 슬러그")
    school_name = models.CharField(max_length=120, blank=True, verbose_name="학교명")
    sync_mode = models.CharField(max_length=30, choices=SYNC_MODE_CHOICES, verbose_name="반영 방식")
    sync_options_text = models.CharField(max_length=120, blank=True, verbose_name="반영 대상 옵션")
    overwrite_existing = models.BooleanField(default=False, verbose_name="기존 고정시간표 덮어쓰기")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="success", verbose_name="결과 상태")
    applied_count = models.PositiveIntegerField(default=0, verbose_name="새로 반영")
    updated_count = models.PositiveIntegerField(default=0, verbose_name="이름 갱신")
    skipped_count = models.PositiveIntegerField(default=0, verbose_name="건너뜀")
    conflict_count = models.PositiveIntegerField(default=0, verbose_name="기존값 충돌")
    room_created_count = models.PositiveIntegerField(default=0, verbose_name="신규 특별실")

    summary_text = models.TextField(blank=True, verbose_name="요약 메모")
    payload = models.JSONField(default=dict, blank=True, verbose_name="추가 기록")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="실행 시각")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "시간표 예약 반영 로그"
        verbose_name_plural = "시간표 예약 반영 로그"

    def __str__(self):
        return f"{self.school_name or self.school_slug} | {self.get_sync_mode_display()} | {self.get_status_display()}"
