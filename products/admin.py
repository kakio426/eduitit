from django.contrib import admin
from .models import Product, UserOwnedProduct

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'icon', 'service_type', 'color_theme', 'display_order', 'price', 'is_active', 'is_featured')
    list_filter = ('is_active', 'is_featured', 'service_type', 'color_theme')
    search_fields = ('title', 'description')
    list_editable = ('display_order', 'is_active', 'is_featured')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'price', 'image')
        }),
        ('Display Settings', {
            'fields': ('icon', 'color_theme', 'card_size', 'display_order')
        }),
        ('Service Configuration', {
            'fields': ('service_type', 'external_url')
        }),
        ('Status', {
            'fields': ('is_active', 'is_featured')
        }),
    )

@admin.register(UserOwnedProduct)
class UserOwnedProductAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'purchased_at')
    list_filter = ('user', 'product')
