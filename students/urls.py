from django.urls import path
from .views import ParentStudentListView, ParentStudentDetailView, ParentStudentGradesView, ParentDashboardView

urlpatterns = [
    path('parent/dashboard/', ParentDashboardView.as_view(), name='parent-dashboard'),
    path('parent/students/', ParentStudentListView.as_view(), name='parent-students'),
    path('parent/students/<int:pk>/', ParentStudentDetailView.as_view(), name='parent-student-detail'),
    path('parent/students/<int:student_id>/grades/', ParentStudentGradesView.as_view(), name='parent-student-grades'),
]

