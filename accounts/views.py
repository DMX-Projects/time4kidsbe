from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.permissions import IsAdminUser
from .serializers import CustomTokenObtainPairSerializer, ParentTokenObtainPairSerializer, UserSerializer
from .models import User


class AdminStatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        from enquiries.models import Enquiry
        from franchises.models import Franchise, ParentProfile

        admin_user = request.user
        active_users = User.objects.filter(is_active=True).count()
        franchise_count = Franchise.objects.filter(admin=admin_user).count()
        enquiries_count = Enquiry.objects.filter(franchise__admin=admin_user).count()
        parents_count = ParentProfile.objects.filter(franchise__admin=admin_user).count()

        return Response(
            {
                "active_users": active_users,
                "franchises": franchise_count,
                "enquiries": enquiries_count,
                "parents": parents_count,
            }
        )


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class ParentLoginView(TokenObtainPairView):
    """Parent-specific login endpoint"""
    serializer_class = ParentTokenObtainPairSerializer


class CurrentUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
