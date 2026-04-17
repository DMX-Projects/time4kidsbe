from django.contrib import admin
from .models import HeroSlide, HomeTestimonial, HomePageContent


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


@admin.register(HomePageContent)
class HomePageContentAdmin(admin.ModelAdmin):
    list_display = ("id", "updated_at")
