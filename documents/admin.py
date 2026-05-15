from django.contrib import admin

from franchises.models import Franchise

from .models import FranchiseDocument, ParentDocument


@admin.register(ParentDocument)
class ParentDocumentAdmin(admin.ModelAdmin):
    list_display = ("get_display_title", "category", "display_franchise", "is_active", "order", "created_at")
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
        raw_title = (obj.title or "").strip() if obj.title is not None else ""
        if obj.category == "HOLIDAY_LISTS":
            state_display = obj.get_state_display() if obj.state else ""
            year = f" ({obj.academic_year})" if obj.academic_year else ""
            return f"{raw_title or state_display}{year}" or "(untitled)"
        return raw_title or "(untitled)"
    get_display_title.short_description = 'Title'

    def display_franchise(self, obj: ParentDocument):
        if not obj.franchise_id:
            return "Global"
        try:
            return obj.franchise.name
        except Franchise.DoesNotExist:
            return f"(missing #{obj.franchise_id})"

    display_franchise.short_description = "Franchise"
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('franchise')


@admin.register(FranchiseDocument)
class FranchiseDocumentAdmin(admin.ModelAdmin):
    list_display = ("category", "display_franchise", "title", "source_path", "is_active", "order", "created_at")
    list_filter = ("category", "franchise", "is_active", "academic_year", "created_at")
    search_fields = ("title", "description", "academic_year", "source_path")
    list_editable = ("is_active", "order")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (
            "Document Information",
            {
                "fields": ("category", "title", "description", "file", "source_path"),
            },
        ),
        (
            "Academic / Metadata",
            {
                "fields": ("academic_year",),
                "description": "Optional academic year (useful for academic documents).",
            },
        ),
        (
            "Organization",
            {
                "fields": ("franchise", "order", "is_active"),
                "description": "Leave franchise blank for global documents accessible to all centres.",
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def display_franchise(self, obj: FranchiseDocument):
        if not obj.franchise_id:
            return "Global"
        try:
            return obj.franchise.name
        except Franchise.DoesNotExist:
            return f"(missing #{obj.franchise_id})"

    display_franchise.short_description = "Franchise"

