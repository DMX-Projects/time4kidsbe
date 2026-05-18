from django.contrib import admin

from .models import Enquiry, FranchiseEnquiry, KidsEnquiry


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


@admin.register(KidsEnquiry)
class KidsEnquiryAdmin(admin.ModelAdmin):
    list_display = ("name", "mobileno", "email", "city", "location", "source", "created_date")
    list_filter = ("source", "enquiry_type", "created_date")
    search_fields = ("name", "mobileno", "email", "location", "centre_name")
    readonly_fields = ("created_date", "raw_payload")
