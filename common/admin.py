from django.contrib import admin
from .models import HeroSlide

@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ('id', 'alt_text', 'order', 'is_active', 'created_at')
    list_editable = ('order', 'is_active')
    search_fields = ('alt_text',)
