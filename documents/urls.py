from django.urls import path
from .views import (
    ParentDocumentListView,
    parent_documents_by_category,
    franchise_documents_by_category,
    FranchiseParentDocumentListCreateView,
    FranchiseParentDocumentDeleteView,
    FranchiseIndentRequestListCreateView,
    AdminIndentRequestListView,
    AdminIndentRequestUpdateView,
)

urlpatterns = [
    path('parent/documents/', ParentDocumentListView.as_view(), name='parent-documents'),
    path('parent/documents/category/<str:category>/', parent_documents_by_category, name='parent-documents-category'),
    path('franchise/documents/category/<str:category>/', franchise_documents_by_category, name='franchise-documents-category'),
    path('franchise/parent-documents/', FranchiseParentDocumentListCreateView.as_view(), name='franchise-parent-documents'),
    path('franchise/parent-documents/<int:pk>/', FranchiseParentDocumentDeleteView.as_view(), name='franchise-parent-documents-delete'),
    path('franchise/indents/', FranchiseIndentRequestListCreateView.as_view(), name='franchise-indent-requests'),
    path('admin/indents/', AdminIndentRequestListView.as_view(), name='admin-indent-requests'),
    path('admin/indents/<int:pk>/', AdminIndentRequestUpdateView.as_view(), name='admin-indent-request-update'),
]

