from django.urls import path

from .views import (
    AdminAllEnquiryListView,
    AdminEnquiryListView,
    EnquiryCreateView,
    EnquiryUpdateView,
    FranchiseEnquiryCreateView,
    FranchiseEnquiryListView,
    FranchiseEnquiryUpdateView,
    FranchiseLeadAdminUpdateView,
    FranchiseLeadPartnerUpdateView,
)

urlpatterns = [
    path("submit/", EnquiryCreateView.as_view(), name="enquiry-create"),
    path("franchise-submit/", FranchiseEnquiryCreateView.as_view(), name="franchise-enquiry-create"),
    path("admin/", AdminEnquiryListView.as_view(), name="enquiry-admin-list"),
    path("admin/all/", AdminAllEnquiryListView.as_view(), name="enquiry-admin-all-list"),
    path("admin/<int:pk>/", EnquiryUpdateView.as_view(), name="enquiry-update"),
    path("admin/franchise/<int:pk>/", FranchiseLeadAdminUpdateView.as_view(), name="franchise-lead-admin-update"),
    path("franchise/", FranchiseEnquiryListView.as_view(), name="enquiry-franchise-list"),
    path("franchise/lead/<int:pk>/", FranchiseLeadPartnerUpdateView.as_view(), name="franchise-lead-partner-update"),
    path("franchise/<int:pk>/", FranchiseEnquiryUpdateView.as_view(), name="enquiry-franchise-update"),
]
