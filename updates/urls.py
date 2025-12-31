from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UpdateViewSet

router = DefaultRouter()
router.register(r'', UpdateViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
