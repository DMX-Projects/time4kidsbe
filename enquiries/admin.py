from django.contrib import admin

from .models import Enquiry, FranchiseEnquiry


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ("enquiry_type", "name", "email", "franchise", "created_at")
    list_filter = ("enquiry_type", "created_at")
    search_fields = ("name", "email", "franchise__name")


@admin.register(FranchiseEnquiry)
class FranchiseEnquiryAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "city", "franchise", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "email", "franchise__name")
