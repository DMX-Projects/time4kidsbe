from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    HeroSlideViewSet,
    HomeTestimonialViewSet,
    HomePageContentView,
    HomePageContentResetView,
)

router = DefaultRouter()
router.register(r'hero-slides', HeroSlideViewSet)
router.register(r'home-testimonials', HomeTestimonialViewSet, basename='home-testimonials')

urlpatterns = [
    path("home-page-content/reset/", HomePageContentResetView.as_view(), name="home-page-content-reset"),
    path("home-page-content/", HomePageContentView.as_view(), name="home-page-content"),
    path('', include(router.urls)),
]
