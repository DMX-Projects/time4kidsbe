from django.urls import path

from .views import AdminStatsView, ParentSelfProfileView

urlpatterns = [
    path("admin/stats/", AdminStatsView.as_view(), name="admin-stats"),
    path("parent/profile/", ParentSelfProfileView.as_view(), name="parent-self-profile"),
]
