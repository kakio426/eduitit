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

class ServiceManualInline(admin.StackedInline):
    model = ServiceManual
    extra = 0
    show_change_link = True
    verbose_name = "서비스 이용방법 (매뉴얼)"
    verbose_name_plural = "서비스 이용방법 (매뉴얼)"
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'is_published')
        }),
    )

@admin.register(ServiceManual)
class ServiceManualAdmin(admin.ModelAdmin):
    list_display = ('product', 'title', 'is_published', 'display_order_display', 'updated_at')
    list_filter = ('is_published', 'product__service_type')
    search_fields = ('title', 'product__title')
    list_editable = ('is_published',)
    inlines = [ManualSectionInline]

    def display_order_display(self, obj):
        return obj.product.display_order
    display_order_display.short_description = '표시 순서(상품 기준)'
    display_order_display.admin_order_field = 'product__display_order'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'icon', 'service_type', 'color_theme', 'display_order', 'price', 'is_active', 'is_featured')
    list_filter = ('is_active', 'is_featured', 'service_type', 'color_theme')
    search_fields = ('title', 'description')
    list_editable = ('service_type', 'icon', 'color_theme', 'display_order', 'is_active', 'is_featured')
    inlines = [ProductFeatureInline, ServiceManualInline]

    fieldsets = (
        ('기본 정보', {
            'fields': ('title', 'lead_text', 'description', 'price', 'image')
        }),
        ('표시 설정', {
            'fields': ('icon', 'color_theme', 'card_size', 'display_order'),
            'description': 'icon: 이모지(🎲) 또는 FontAwesome 클래스(fa-solid fa-dice)'
        }),
        ('서비스 분류', {
            'fields': ('service_type', 'external_url', 'launch_route_name'),
            'description': '카테고리를 선택하면 홈 화면 탭 필터에 반영됩니다.'
        }),
        ('V2 홈 목적별 섹션', {
            'fields': ('solve_text', 'result_text', 'time_text'),
            'description': '홈 V2 미니 카드에 표시될 텍스트. 비워두면 description이 fallback으로 표시됩니다.',
            'classes': ('collapse',),
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
