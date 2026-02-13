from django.contrib import admin
from .models import Product, UserOwnedProduct, ProductFeature, ServiceManual, ManualSection

class ProductFeatureInline(admin.TabularInline):
    model = ProductFeature
    extra = 3

class ManualSectionInline(admin.StackedInline):
    model = ManualSection
    extra = 1
    fieldsets = (
        ('섹션 설정', {
            'fields': ('title', 'layout_type', 'badge_text', 'display_order')
        }),
        ('콘텐츠', {
            'fields': ('content', 'image', 'video_url')
        }),
    )

@admin.register(ServiceManual)
class ServiceManualAdmin(admin.ModelAdmin):
    list_display = ('product', 'title', 'is_published', 'updated_at')
    list_filter = ('is_published', 'product__service_type')
    search_fields = ('title', 'product__title')
    inlines = [ManualSectionInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'icon', 'service_type', 'color_theme', 'display_order', 'price', 'is_active', 'is_featured')
    list_filter = ('is_active', 'is_featured', 'service_type', 'color_theme')
    search_fields = ('title', 'description')
    list_editable = ('service_type', 'icon', 'color_theme', 'display_order', 'is_active', 'is_featured')
    inlines = [ProductFeatureInline]

    fieldsets = (
        ('기본 정보', {
            'fields': ('title', 'lead_text', 'description', 'price', 'image')
        }),
        ('표시 설정', {
            'fields': ('icon', 'color_theme', 'card_size', 'display_order'),
            'description': 'icon: 이모지(🎲) 또는 FontAwesome 클래스(fa-solid fa-dice)'
        }),
        ('서비스 분류', {
            'fields': ('service_type', 'external_url'),
            'description': '카테고리를 선택하면 홈 화면 탭 필터에 반영됩니다.'
        }),
        ('상태', {
            'fields': ('is_active', 'is_featured', 'is_guest_allowed')
        }),
    )

@admin.register(UserOwnedProduct)
class UserOwnedProductAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'purchased_at')
    list_filter = ('user', 'product')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'product')
