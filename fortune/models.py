from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class Stem(models.Model):
    """Ten Heavenly Stems (천간)"""
    name = models.CharField(max_length=10, help_text="English name e.g. Gap") 
    character = models.CharField(max_length=2, help_text="Hanja e.g. 甲") 
    polarity = models.CharField(max_length=10, choices=[('yang', 'Yang'), ('yin', 'Yin')]) 
    element = models.CharField(max_length=10, choices=[('wood', 'Wood'), ('fire', 'Fire'), ('earth', 'Earth'), ('metal', 'Metal'), ('water', 'Water')])

    def __str__(self):
        return self.character

class Branch(models.Model):
    """Twelve Earthly Branches (지지)"""
    name = models.CharField(max_length=10, help_text="English name e.g. Ja") 
    character = models.CharField(max_length=2, help_text="Hanja e.g. 子") 
    polarity = models.CharField(max_length=10, choices=[('yang', 'Yang'), ('yin', 'Yin')])
    element = models.CharField(max_length=10, choices=[('wood', 'Wood'), ('fire', 'Fire'), ('earth', 'Earth'), ('metal', 'Metal'), ('water', 'Water')])
    
    class Meta:
        verbose_name_plural = "Branches"

    def __str__(self):
        return self.character

class SixtyJiazi(models.Model):
    """60 Jiazi (육십갑자)"""
    name = models.CharField(max_length=20, help_text="English name e.g. GapJa")
    stem = models.ForeignKey(Stem, on_delete=models.CASCADE)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    na_yin_element = models.CharField(max_length=20, help_text="Na-Yin Element (납음오행)", blank=True, null=True)

    class Meta:
        verbose_name_plural = "Sixty Jiazi"

    def __str__(self):
        return f"{self.stem.character}{self.branch.character}"

class InterpretationRule(models.Model):
    """Configuration for Saju Interpretation Rules (RAG)"""
    TRIGGER_TYPES = [
        ('TEN_GOD', 'Ten Gods Interaction'),
        ('DM_STRENGTH', 'Day Master Strength'),
        ('GANJI', 'Specific Pillar')
    ]
    
    rule_id = models.AutoField(primary_key=True)
    trigger_type = models.CharField(max_length=20, choices=TRIGGER_TYPES)
    
    # Conditions
    element_1 = models.CharField(max_length=50, blank=True, help_text="Subject (e.g. Day Master)")
    element_2 = models.CharField(max_length=50, blank=True, help_text="Object (e.g. Month Branch or Ten God)")
    condition_json = models.JSONField(default=dict, blank=True, help_text="e.g. {'strength': 'Weak'}")
    
    # Content
    base_interpretation = models.TextField(help_text="Core fact for LLM")
    advice_template = models.TextField(blank=True)
    severity_score = models.IntegerField(default=5)

    def __str__(self):
        return f"[{self.trigger_type}] {self.element_1} vs {self.element_2}"


class FortuneResult(models.Model):
    """사용자가 저장한 사주/운세 결과"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_fortunes')
    mode = models.CharField(max_length=20, choices=[('teacher', '교사 모드'), ('general', '일반 모드'), ('daily', '일진 모드')])
    result_text = models.TextField(help_text="AI가 생성한 분석 결과 내용")
    target_date = models.DateField(null=True, blank=True, help_text="일진 모드인 경우 해당 날짜")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        date_str = self.target_date.strftime('%Y-%m-%d') if self.target_date else "원국"
        return f"[{self.get_mode_display()}] {self.user.username} - {date_str}"


class FortunePseudonymousCache(models.Model):
    """개인정보 원문 없이 결과 재사용을 위한 사용자별 비식별 캐시"""

    PURPOSE_FULL = 'full'
    PURPOSE_DAILY = 'daily'
    PURPOSE_CHOICES = [
        (PURPOSE_FULL, '전체 사주'),
        (PURPOSE_DAILY, '일진'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fortune_pseudonymous_caches')
    purpose = models.CharField(max_length=10, choices=PURPOSE_CHOICES)
    fingerprint = models.CharField(max_length=64)
    result_text = models.TextField()
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'purpose', 'fingerprint'], name='fortune_cache_user_purpose_fingerprint_uniq'),
        ]
        indexes = [
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"{self.user.username} {self.purpose} cache"

class ZooResult(models.Model):
    """사용자가 저장한 티처블 동물원(MBTI) 결과"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='zoo_results')
    mbti_type = models.CharField(max_length=4, help_text="e.g. ENFP")
    animal_name = models.CharField(max_length=50, help_text="e.g. 해달")
    result_text = models.TextField(help_text="AI가 생성한 분석 결과 내용")
    answers_json = models.JSONField(help_text="사용자가 선택한 답변들", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.animal_name}({self.mbti_type})"

class FavoriteDate(models.Model):
    """사용자가 즐겨찾기한 날짜 (시험일, 생일, 기념일 등)"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorite_dates')
    date = models.DateField()
    label = models.CharField(max_length=50, help_text="날짜 라벨 (예: 시험일, 생일)")
    memo = models.TextField(blank=True, help_text="메모")
    color = models.CharField(max_length=20, default='indigo', help_text="UI 색상")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date']
        unique_together = ['user', 'date', 'label']

    def __str__(self):
        return f"{self.user.username} - {self.label} ({self.date})"

class DailyFortuneLog(models.Model):
    """일진 조회 기록 (통계용)"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fortune_logs')
    target_date = models.DateField()
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-viewed_at']

    def __str__(self):
        return f"{self.user.username} - {self.target_date}"
