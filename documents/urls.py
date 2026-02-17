from django.urls import path
from .views import ParentDocumentListView, parent_documents_by_category

urlpatterns = [
    path('parent/documents/', ParentDocumentListView.as_view(), name='parent-documents'),
    path('parent/documents/category/<str:category>/', parent_documents_by_category, name='parent-documents-category'),
]

