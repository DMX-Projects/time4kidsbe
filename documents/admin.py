from django.contrib import admin
from .models import ParentDocument


@admin.register(ParentDocument)
class ParentDocumentAdmin(admin.ModelAdmin):
    list_display = ('get_display_title', 'category', 'franchise', 'is_active', 'order', 'created_at')
    list_filter = ('category', 'franchise', 'is_active', 'state', 'created_at')
    search_fields = ('title', 'description', 'academic_year', 'state')
    list_editable = ('is_active', 'order')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Document Information', {
            'fields': ('category', 'title', 'description', 'file', 'thumbnail')
        }),
        ('Holiday List Details', {
            'fields': ('state', 'academic_year'),
            'description': 'Fill these fields only when category is "Holiday Lists"',
            'classes': ('collapse',)
        }),
        ('Organization', {
            'fields': ('franchise', 'order', 'is_active'),
            'description': 'Leave franchise blank for global documents accessible to all parents'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_display_title(self, obj):
        """Display title with state/academic year for holiday lists"""
        if obj.category == 'HOLIDAY_LISTS':
            state_display = obj.get_state_display() if obj.state else ''
            year = f" ({obj.academic_year})" if obj.academic_year else ''
            return f"{obj.title or state_display}{year}"
        return obj.title
    get_display_title.short_description = 'Title'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('franchise')

