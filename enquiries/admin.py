from django.contrib import admin

from .models import Enquiry


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ("enquiry_type", "name", "email", "franchise", "created_at")
    list_filter = ("enquiry_type", "created_at")
    search_fields = ("name", "email", "franchise__name")
