from django.db import models

class Achievement(models.Model):
    title = models.CharField(max_length=200, verbose_name="수상/활동명")
    issuer = models.CharField(max_length=200, verbose_name="발행 기관/주최")
    date_awarded = models.DateField(verbose_name="수상/활동 일자")
    description = models.TextField(blank=True, verbose_name="설명")
    image = models.ImageField(
        upload_to='portfolio/achievements/',
        max_length=500,
        null=True,
        blank=True,
        verbose_name="상장/증빙 이미지",
    )
    image_caption = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="대표 이미지 설명",
        help_text="포트폴리오 카드의 대표 이미지 아래에 바로 노출되는 짧은 설명입니다.",
    )
    
    is_featured = models.BooleanField(default=False, verbose_name="메인 노출 여부")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "수상 및 활동 실적"
        verbose_name_plural = "수상 및 활동 실적"
        ordering = ['-date_awarded']

    def __str__(self):
        return f"{self.title} ({self.issuer})"

    @property
    def safe_image_url(self):
        """Broken media reference should not break the entire portfolio page."""
        if not self.image:
            return ""
        try:
            return self.image.url
        except Exception:
            return ""

    @property
    def display_image_caption(self):
        return (self.image_caption or self.title).strip()

    @property
    def gallery_images(self):
        images = []

        cover_url = self.safe_image_url
        if cover_url:
            cover_caption = self.display_image_caption
            images.append(
                {
                    "url": cover_url,
                    "alt": cover_caption,
                    "caption": cover_caption,
                    "badge": "대표 자료",
                    "is_cover": True,
                }
            )

        photos = getattr(self, "prefetched_photos", None)
        if photos is None:
            photos = self.photos.all()

        for photo in photos:
            photo_url = photo.safe_image_url
            if not photo_url:
                continue
            photo_caption = (photo.caption or self.title).strip()
            images.append(
                {
                    "url": photo_url,
                    "alt": photo_caption,
                    "caption": photo_caption,
                    "badge": "현장 사진",
                    "is_cover": False,
                }
            )

        return images


class AchievementPhoto(models.Model):
    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.CASCADE,
        related_name="photos",
        verbose_name="연결 실적",
    )
    image = models.ImageField(
        upload_to="portfolio/achievements/",
        max_length=500,
        verbose_name="추가 사진",
    )
    caption = models.CharField(max_length=200, blank=True, verbose_name="사진 설명")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="정렬 순서")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "실적 사진"
        verbose_name_plural = "실적 사진"
        ordering = ["sort_order", "id"]

    def __str__(self):
        if self.caption:
            return f"{self.achievement.title} - {self.caption}"
        return f"{self.achievement.title} - 사진 {self.pk or '신규'}"

    @property
    def safe_image_url(self):
        if not self.image:
            return ""
        try:
            return self.image.url
        except Exception:
            return ""

class LectureProgram(models.Model):
    title = models.CharField(max_length=200, verbose_name="강의명")
    description = models.TextField(verbose_name="강의 개요")
    target_audience = models.CharField(max_length=200, verbose_name="교육 대상")
    duration = models.CharField(max_length=100, verbose_name="소요 시간")
    syllabus = models.TextField(verbose_name="커리큘럼")
    thumbnail = models.ImageField(
        upload_to='portfolio/thumbnails/',
        max_length=500,
        null=True,
        blank=True,
        verbose_name="썸네일",
    )
    
    is_active = models.BooleanField(default=True, verbose_name="노출 여부")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "강의 프로그램"
        verbose_name_plural = "강의 프로그램"
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def safe_thumbnail_url(self):
        """Broken media reference should not break the entire portfolio page."""
        if not self.thumbnail:
            return ""
        try:
            return self.thumbnail.url
        except Exception:
            return ""

class LectureHistory(models.Model):
    program = models.ForeignKey(LectureProgram, on_delete=models.SET_NULL, null=True, related_name='histories', verbose_name="관련 프로그램")
    date = models.DateField(verbose_name="강의 일자")
    client_name = models.CharField(max_length=200, verbose_name="의뢰처/기관")
    participants_count = models.PositiveIntegerField(default=0, verbose_name="참여 인원")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "강의 이력"
        verbose_name_plural = "강의 이력"
        ordering = ['-date']

    def __str__(self):
        return f"{self.date} - {self.client_name} ({self.program.title if self.program else '기타'})"

class Inquiry(models.Model):
    name = models.CharField(max_length=100, verbose_name="성함")
    organization = models.CharField(max_length=200, verbose_name="소속 기관/단체")
    email = models.EmailField(verbose_name="이메일")
    phone = models.CharField(max_length=20, verbose_name="연락처")
    requested_date = models.DateField(verbose_name="희망 일시 (선택)", null=True, blank=True)
    topic = models.CharField(max_length=200, verbose_name="제안 및 문의 주제")
    message = models.TextField(verbose_name="상세 내용")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="접수 일시")
    is_reviewed = models.BooleanField(default=False, verbose_name="검토 완료")

    class Meta:
        verbose_name = "협업 제안 및 문의"
        verbose_name_plural = "협업 제안 및 문의"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.organization}) - {self.topic}"
