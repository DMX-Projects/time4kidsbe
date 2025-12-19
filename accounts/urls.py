from django.urls import path

from .views import AdminStatsView

urlpatterns = [
	path("admin/stats/", AdminStatsView.as_view(), name="admin-stats"),
]
