from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import HeroSlideViewSet

router = DefaultRouter()
router.register(r'hero-slides', HeroSlideViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
