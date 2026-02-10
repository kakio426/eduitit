from django.contrib import admin
from django.db.models import Count
from .models import CollectionRequest, Submission


@admin.register(CollectionRequest)
class CollectionRequestAdmin(admin.ModelAdmin):
    list_display = ['title', 'creator', 'access_code', 'status', 'submission_count_display', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['title', 'creator__username']
    readonly_fields = ['id', 'access_code', 'created_at', 'updated_at']
    raw_id_fields = ['creator']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('creator').annotate(
            _submission_count=Count('submissions', distinct=True)
        )

    def submission_count_display(self, obj):
        return obj._submission_count
    submission_count_display.short_description = '제출 수'
    submission_count_display.admin_order_field = '_submission_count'


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ['contributor_name', 'submission_type', 'collection_request', 'submitted_at']
    list_filter = ['submission_type', 'submitted_at']
    search_fields = ['contributor_name', 'contributor_affiliation']
    readonly_fields = ['id', 'submitted_at']
    raw_id_fields = ['collection_request']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('collection_request')
