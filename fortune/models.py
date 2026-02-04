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

class SajuProfile(models.Model):
    """User's specific Saju data"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='saju_profile')
    birth_date_gregorian = models.DateTimeField(help_text="Gregorian Birth Date and Time")
    gender = models.CharField(max_length=10, choices=[('M', 'Male'), ('F', 'Female')])
    birth_city = models.CharField(max_length=100, help_text="City of Birth for Time Correction")
    longitude = models.FloatField(help_text="Longitude for True Solar Time calculation")

    def __str__(self):
        return f"{self.user.username}'s Saju Profile"

class NatalChart(models.Model):
    """Calculated Natal Chart (Saju Palja)"""
    saju_profile = models.ForeignKey(SajuProfile, on_delete=models.CASCADE, related_name='natal_charts')
    
    # Year Pillar
    year_stem = models.ForeignKey(Stem, related_name='year_stems', on_delete=models.CASCADE)
    year_branch = models.ForeignKey(Branch, related_name='year_branches', on_delete=models.CASCADE)
    
    # Month Pillar
    month_stem = models.ForeignKey(Stem, related_name='month_stems', on_delete=models.CASCADE)
    month_branch = models.ForeignKey(Branch, related_name='month_branches', on_delete=models.CASCADE)
    
    # Day Pillar
    day_stem = models.ForeignKey(Stem, related_name='day_stems', on_delete=models.CASCADE)
    day_branch = models.ForeignKey(Branch, related_name='day_branches', on_delete=models.CASCADE)
    
    # Hour Pillar
    hour_stem = models.ForeignKey(Stem, related_name='hour_stems', on_delete=models.CASCADE)
    hour_branch = models.ForeignKey(Branch, related_name='hour_branches', on_delete=models.CASCADE)
    
    day_master_strength = models.CharField(
        max_length=20, 
        choices=[
            ('ExtremeWeak', 'ExtremeWeak'), 
            ('Weak', 'Weak'), 
            ('Balanced', 'Balanced'), 
            ('Strong', 'Strong'), 
            ('ExtremeStrong', 'ExtremeStrong')
        ]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chart for {self.saju_profile.user.username} ({self.created_at})"

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
    mode = models.CharField(max_length=20, default='general', choices=[('teacher', '교사 모드'), ('general', '일반 모드'), ('daily', '일진 모드')])
    topic = models.CharField(max_length=20, null=True, blank=True, choices=[
        ('total', '전체'),
        ('personality', '성격'),
        ('wealth', '재물'),
        ('career', '직업'),
        ('teacher', '교직 운세'),
        ('compatibility', '연애/인연'),
        ('daily', '일진')
    ], help_text="분석 주제")
    natal_chart = models.JSONField(help_text="저장 당시의 사주 원국 간지")
    result_text = models.TextField(help_text="AI가 생성한 분석 결과 내용")
    target_date = models.DateField(null=True, blank=True, help_text="일진 모드인 경우 해당 날짜")
    natal_hash = models.CharField(max_length=64, null=True, blank=True, db_index=True, help_text="사주 명식 고유 해시 (캐싱용)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        date_str = self.target_date.strftime('%Y-%m-%d') if self.target_date else "원국"
        topic_str = self.get_topic_display() if self.topic else self.get_mode_display()
        return f"[{topic_str}] {self.user.username} - {date_str}"

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

class UserSajuProfile(models.Model):
    """사용자가 저장한 여러 사주 프로필 (나, 가족, 친구 등)"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saju_profiles')
    profile_name = models.CharField(max_length=20, help_text="프로필 이름 (예: 나, 엄마, 친구)")
    person_name = models.CharField(max_length=20, help_text="실제 이름")
    gender = models.CharField(max_length=10, choices=[('male', '남자'), ('female', '여자')])
    birth_year = models.IntegerField()
    birth_month = models.IntegerField()
    birth_day = models.IntegerField()
    birth_hour = models.IntegerField(null=True, blank=True)
    birth_minute = models.IntegerField(null=True, blank=True)
    calendar_type = models.CharField(max_length=10, choices=[('solar', '양력'), ('lunar', '음력')], default='solar')
    natal_chart = models.JSONField(help_text="계산된 사주 팔자", null=True, blank=True)
    is_default = models.BooleanField(default=False, help_text="기본 프로필 여부")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-created_at']
        unique_together = ['user', 'profile_name']

    def __str__(self):
        return f"{self.user.username} - {self.profile_name} ({self.person_name})"

    def save(self, *args, **kwargs):
        # 기본 프로필 설정 시 다른 프로필의 is_default를 False로
        if self.is_default:
            UserSajuProfile.objects.filter(user=self.user, is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

class FavoriteDate(models.Model):
    """사용자가 즐겨찾기한 날짜 (시험일, 생일, 기념일 등)"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorite_dates')
    profile = models.ForeignKey(UserSajuProfile, on_delete=models.CASCADE, related_name='favorite_dates', null=True, blank=True)
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
    profile = models.ForeignKey(UserSajuProfile, on_delete=models.SET_NULL, null=True, blank=True)
    target_date = models.DateField()
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-viewed_at']

    def __str__(self):
        return f"{self.user.username} - {self.target_date}"
