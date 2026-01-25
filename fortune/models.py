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
