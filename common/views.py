from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from accounts.models import UserRole
from accounts.permissions import IsAdminUser
from .models import HeroSlide, HomeTestimonial
from .serializers import HeroSlideSerializer, HomeTestimonialSerializer


class HeroSlideViewSet(viewsets.ModelViewSet):
    """Public list/retrieve: active slides only. Authenticated admin: all slides. Writes: admin only."""

    queryset = HeroSlide.objects.all()
    serializer_class = HeroSlideSerializer
    pagination_class = None

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAdminUser()]

    def get_queryset(self):
        qs = HeroSlide.objects.all().order_by("order", "-created_at")
        if self.action in ("list", "retrieve"):
            user = self.request.user
            if user.is_authenticated and getattr(user, "role", None) == UserRole.ADMIN:
                return qs
            return qs.filter(is_active=True)
        return qs


class HomeTestimonialViewSet(viewsets.ModelViewSet):
    """Public list shows active quotes; admin can list all and create/update/delete."""

    serializer_class = HomeTestimonialSerializer
    pagination_class = None

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsAdminUser()]

    def get_queryset(self):
        qs = HomeTestimonial.objects.all().order_by("order", "id")
        if self.action in ("list", "retrieve"):
            user = self.request.user
            if user.is_authenticated and getattr(user, "role", None) == UserRole.ADMIN:
                return qs
            return qs.filter(is_active=True)
        return qs
