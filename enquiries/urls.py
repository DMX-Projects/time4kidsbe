from django.urls import path

from .views import AdminAllEnquiryListView, AdminEnquiryListView, EnquiryCreateView, FranchiseEnquiryListView, EnquiryUpdateView

urlpatterns = [
    path("submit/", EnquiryCreateView.as_view(), name="enquiry-create"),
    path("admin/", AdminEnquiryListView.as_view(), name="enquiry-admin-list"),
    path("admin/all/", AdminAllEnquiryListView.as_view(), name="enquiry-admin-all-list"),
    path("admin/<int:pk>/", EnquiryUpdateView.as_view(), name="enquiry-update"),
    path("franchise/", FranchiseEnquiryListView.as_view(), name="enquiry-franchise-list"),
]
