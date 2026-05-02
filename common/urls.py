from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    HeroSlideViewSet,
    HomeTestimonialViewSet,
    HomePageContentView,
    HomePageContentResetView,
    PageContentView,
    MarketingAssetViewSet,
)

router = DefaultRouter()
router.register(r'hero-slides', HeroSlideViewSet, basename='hero-slides')
router.register(r'home-testimonials', HomeTestimonialViewSet, basename='home-testimonials')
router.register(r'marketing-assets', MarketingAssetViewSet, basename='marketing-assets')

urlpatterns = [
    path("home-page-content/reset/", HomePageContentResetView.as_view(), name="home-page-content-reset"),
    path("home-page-content/", HomePageContentView.as_view(), name="home-page-content"),
    path("page-content/<slug:slug>/", PageContentView.as_view(), name="page-content"),
    path('', include(router.urls)),
]
