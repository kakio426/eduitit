from django.db import models

class Achievement(models.Model):
    title = models.CharField(max_length=200, verbose_name="수상/활동명")
    issuer = models.CharField(max_length=200, verbose_name="발행 기관/주최")
    date_awarded = models.DateField(verbose_name="수상/활동 일자")
    description = models.TextField(blank=True, verbose_name="설명")
    image = models.ImageField(upload_to='portfolio/achievements/', null=True, blank=True, verbose_name="상장/증빙 이미지")
    
    is_featured = models.BooleanField(default=False, verbose_name="메인 노출 여부")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "수상 및 활동 실적"
        verbose_name_plural = "수상 및 활동 실적"
        ordering = ['-date_awarded']

    def __str__(self):
        return f"{self.title} ({self.issuer})"

class LectureProgram(models.Model):
    title = models.CharField(max_length=200, verbose_name="강의명")
    description = models.TextField(verbose_name="강의 개요")
    target_audience = models.CharField(max_length=200, verbose_name="교육 대상")
    duration = models.CharField(max_length=100, verbose_name="소요 시간")
    syllabus = models.TextField(verbose_name="커리큘럼")
    thumbnail = models.ImageField(upload_to='portfolio/thumbnails/', null=True, blank=True, verbose_name="썸네일")
    
    is_active = models.BooleanField(default=True, verbose_name="노출 여부")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "강의 프로그램"
        verbose_name_plural = "강의 프로그램"
        ordering = ['-created_at']

    def __str__(self):
        return self.title

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
    organization = models.CharField(max_length=200, verbose_name="소속 기관")
    email = models.EmailField(verbose_name="이메일")
    phone = models.CharField(max_length=20, verbose_name="연락처")
    requested_date = models.DateField(verbose_name="희망 강의 일자", null=True, blank=True)
    topic = models.CharField(max_length=200, verbose_name="강의 주제/목적")
    message = models.TextField(verbose_name="전하실 말씀")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="접수 일시")
    is_reviewed = models.BooleanField(default=False, verbose_name="검토 완료")

    class Meta:
        verbose_name = "섭외 요청"
        verbose_name_plural = "섭외 요청"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.organization}) - {self.topic}"
