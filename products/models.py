from django.db import models
from django.contrib.auth.models import User

class Product(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    
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
        ('game', 'Game'),
        ('tool', 'Tool'),
        ('platform', 'Platform'),
        ('library', 'Library'),
        ('guide', 'Guide'),
    ]
    
    icon = models.CharField(max_length=50, default='🛠️', help_text="Emoji or FontAwesome class for card icon")
    color_theme = models.CharField(max_length=20, choices=COLOR_CHOICES, default='purple', help_text="Color theme")
    card_size = models.CharField(max_length=20, choices=SIZE_CHOICES, default='small', help_text="Card size")
    display_order = models.IntegerField(default=0, help_text="Order in which to display (lower numbers first)")
    service_type = models.CharField(max_length=20, choices=SERVICE_CHOICES, default='tool', help_text="Service type")
    external_url = models.URLField(blank=True, help_text="External URL for services hosted elsewhere")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

class UserOwnedProduct(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_products')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    purchased_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')

    def __str__(self):
        return f"{self.user.username} - {self.product.title}"
