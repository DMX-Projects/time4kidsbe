from django.contrib import admin
from .models import HeroSlide, HomeTestimonial, HomePageContent, Holiday, PageContent, MarketingAsset, StudentsKitPage, State, City


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "state")
    list_filter = ("state",)
    search_fields = ("name", "state__name")
    ordering = ("state__name", "name")
    autocomplete_fields = ("state",)


@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ('id', 'alt_text', 'order', 'is_active', 'created_at')
    list_editable = ('order', 'is_active')
    search_fields = ('alt_text',)


@admin.register(HomeTestimonial)
class HomeTestimonialAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "relation", "order", "is_active", "updated_at")
    list_editable = ("order", "is_active")
    search_fields = ("author", "text", "relation")


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ('state', 'academic_year', 'is_active', 'updated_at')
    list_filter = ('state', 'academic_year', 'is_active')
    search_fields = ('title', 'academic_year')


@admin.register(HomePageContent)
class HomePageContentAdmin(admin.ModelAdmin):
    list_display = ("id", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).defer("data")

    def has_add_permission(self, request):
        return not HomePageContent.objects.exists()


@admin.register(PageContent)
class PageContentAdmin(admin.ModelAdmin):
    list_display = ('slug', 'updated_at')
    search_fields = ('slug',)


@admin.register(StudentsKitPage)
class StudentsKitPageAdmin(admin.ModelAdmin):
    list_display = ("short_label", "slug", "public_path", "is_active", "updated_at")
    list_editable = ("is_active",)
    search_fields = ("title", "slug", "row_key")
    readonly_fields = ("slug", "public_path", "row_key")


@admin.register(MarketingAsset)
class MarketingAssetAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'is_active', 'updated_at')
    list_editable = ('is_active',)
    search_fields = ('title', 'slug')
    prepopulated_fields = {'slug': ('title',)}
