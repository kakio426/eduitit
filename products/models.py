from django.db import models
from django.contrib.auth.models import User

class Product(models.Model):
    title = models.CharField(max_length=200)
    lead_text = models.TextField(blank=True, help_text="Short lead text for modal display")
    description = models.TextField()
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    is_guest_allowed = models.BooleanField(default=False, help_text="비회원 체험 가능 여부")
    
    # Display metadata fields
    COLOR_CHOICES = [
        ('purple', 'Purple'),
        ('green', 'Green'),
        ('red', 'Red'),
        ('orange', 'Orange'),
        ('blue', 'Blue'),
        ('dark', 'Dark'),
    ]
    
    SIZE_CHOICES = [
        ('small', 'Small (1x1)'),
        ('wide', 'Wide (2x1)'),
        ('tall', 'Tall (1x2)'),
        ('hero', 'Hero (2x2)'),
    ]
    
    SERVICE_CHOICES = [
        ('classroom', '운영과 수업'),
        ('work', '업무경감'),
        ('game', '게임모음'),
        ('counsel', '상담·운세'),
        ('edutech', '에듀테크'),
        ('etc', '기타'),
    ]
    
    icon = models.CharField(max_length=50, default='🛠️', help_text="Emoji or FontAwesome class for card icon")
    color_theme = models.CharField(max_length=20, choices=COLOR_CHOICES, default='purple', help_text="Color theme")
    card_size = models.CharField(max_length=20, choices=SIZE_CHOICES, default='small', help_text="Card size")
    display_order = models.IntegerField(default=0, help_text="Order in which to display (lower numbers first)")
    service_type = models.CharField(max_length=20, choices=SERVICE_CHOICES, default='etc', help_text="서비스 카테고리")
    external_url = models.URLField(blank=True, help_text="External URL for services hosted elsewhere")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

class ProductFeature(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='features')
    icon = models.CharField(max_length=50, help_text="Emoji or FontAwesome class")
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    def __str__(self):
        return f"{self.product.title} - {self.title}"

class UserOwnedProduct(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_products')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    purchased_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')

    def __str__(self):
        return f"{self.user.username} - {self.product.title}"

# --- DutyTicker Models ---

class DTSettings(models.Model):
    """User-specific settings for DutyTicker"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='dutyticker_settings')
    auto_rotation = models.BooleanField(default=False, help_text="Automatically rotate roles daily/weekly")
    rotation_frequency = models.CharField(
        max_length=20, 
        choices=[('daily', 'Daily'), ('weekly', 'Weekly')], 
        default='daily'
    )
    last_rotation_date = models.DateField(null=True, blank=True)
    last_broadcast_message = models.TextField(blank=True, help_text="Persisted broadcast message")
    mission_title = models.CharField(max_length=200, default="오늘도 행복한 우리 교실", help_text="Main display mission title")
    mission_desc = models.TextField(default="선생님 말씀에 집중해 주세요.", help_text="Main display mission description")
    
    def __str__(self):
        return f"{self.user.username}'s Settings"

class DTStudent(models.Model):
    """Student roster for each teacher"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dt_students')
    name = models.CharField(max_length=100)
    number = models.IntegerField(default=0, help_text="Student number for ordering")
    is_active = models.BooleanField(default=True)
    is_mission_completed = models.BooleanField(default=False, help_text="Daily mission completion status")
    
    class Meta:
        ordering = ['number', 'name']
        
    def __str__(self):
        return self.name

class DTRole(models.Model):
    """Duty roles defined by the teacher"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dt_roles')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    time_slot = models.CharField(max_length=50, default="쉬는시간", help_text="When to perform this role")
    icon = models.CharField(max_length=50, blank=True, default="📋")
    color = models.CharField(max_length=50, blank=True, default="bg-white")
    
    def __str__(self):
        return self.name

class DTRoleAssignment(models.Model):
    """Assignment of a role to a student for a specific period"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dt_assignments')
    role = models.ForeignKey(DTRole, on_delete=models.CASCADE)
    student = models.ForeignKey(DTStudent, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateField(auto_now_add=True) # Assignments are typically daily, but tracked
    is_completed = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('user', 'role', 'date') 
        # Ideally one assignment per role per day, but we might simply update the current assignment without date constraint if it's strictly state-based.
        # However, for history or rotation, date is good. For now, let's keep it simple: current state.
        # Actually, let's just model *Current* assignment. History can be another table if needed.
        # Let's drop 'date' uniqueness for now and just rely on logic to fetch the "latest" or "active".
        # Better yet: One assignment object per role that gets UPDATED, or new ones created?
        # Let's stick to: This table holds the CURRENT configuration.
    
    def __str__(self):
        return f"{self.role.name} - {self.student.name if self.student else 'Unassigned'}"

class DTSchedule(models.Model):
    """Weekly schedule"""
    DAYS_OF_WEEK = [
        (0, 'Sunday'),
        (1, 'Monday'),
        (2, 'Tuesday'),
        (3, 'Wednesday'),
        (4, 'Thursday'),
        (5, 'Friday'),
        (6, 'Saturday'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dt_schedules')
    day = models.IntegerField(choices=DAYS_OF_WEEK)
    period = models.IntegerField(help_text="1 for 1st period, etc.")
    subject = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    class Meta:
        ordering = ['day', 'period']
        
    def __str__(self):
        return f"{self.get_day_display()} {self.period} - {self.subject}"
