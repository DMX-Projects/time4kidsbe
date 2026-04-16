from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import HeroSlideViewSet, HomeTestimonialViewSet

router = DefaultRouter()
router.register(r'hero-slides', HeroSlideViewSet)
router.register(r'home-testimonials', HomeTestimonialViewSet, basename='home-testimonials')

urlpatterns = [
    path('', include(router.urls)),
]
