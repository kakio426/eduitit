from django.contrib import admin
from .models import Product, UserOwnedProduct

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'price', 'is_active', 'is_featured', 'created_at')
    list_filter = ('is_active', 'is_featured')
    search_fields = ('title', 'description')

@admin.register(UserOwnedProduct)
class UserOwnedProductAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'purchased_at')
    list_filter = ('user', 'product')
