from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.permissions import IsAdminUser, IsParentUser
from accounts.profile_access import parent_profile_for_user

from .serializers import CustomTokenObtainPairSerializer, ParentTokenObtainPairSerializer, UserSerializer
from .models import User
from django.contrib.auth.password_validation import validate_password
from django.db.models import Q


class AdminStatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        from enquiries.models import Enquiry
        from franchises.models import Franchise, ParentProfile

        admin_user = request.user
        # Site-wide active accounts (all roles)
        active_users = User.objects.filter(is_active=True).count()
        # Match AdminFranchiseViewSet list: all franchises an admin may manage
        franchise_count = Franchise.objects.count()
        # Global enquiries + enquiries tied to franchises owned by this admin
        enquiries_count = (
            Enquiry.objects.filter(Q(franchise__isnull=True) | Q(franchise__admin=admin_user))
            .distinct()
            .count()
        )
        parents_count = ParentProfile.objects.filter(franchise__admin=admin_user).count()

        return Response(
            {
                "active_users": active_users,
                "franchises": franchise_count,
                "enquiries": enquiries_count,
                "parents": parents_count,
            }
        )


@method_decorator(csrf_exempt, name='dispatch')
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


@method_decorator(csrf_exempt, name='dispatch')
class ParentLoginView(TokenObtainPairView):
    """Parent-specific login endpoint"""
    serializer_class = ParentTokenObtainPairSerializer


@method_decorator(csrf_exempt, name='dispatch')
class CurrentUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


@method_decorator(csrf_exempt, name="dispatch")
class PasswordResetRequestView(APIView):
    """
    Request password reset by email.
    Always returns a generic response to avoid user enumeration.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        identifier = request.data.get("email") or request.data.get("identifier")
        if not identifier:
            return Response({"detail": "Email is required."}, status=400)

        # Accept either email or username
        user = User.objects.filter(email__iexact=identifier).first()
        if not user:
            user = User.objects.filter(username__iexact=identifier).first()

        if user and user.is_active:
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)

            # Use the first trusted origin as the frontend base for the reset link.
            frontend_base = None
            try:
                frontend_base = settings.CSRF_TRUSTED_ORIGINS[0]
            except Exception:
                frontend_base = None
            if not frontend_base:
                frontend_base = "http://localhost:3000"

            reset_url = f"{frontend_base}/reset-password?uid={uidb64}&token={token}"

            subject = "T.I.M.E. Kids - Password Reset"
            message = (
                f"Hi,\n\n"
                f"You requested a password reset for your account.\n\n"
                f"Reset link:\n{reset_url}\n\n"
                f"If you did not request this, please ignore this email.\n"
            )

            try:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@time4kids.app"),
                    recipient_list=[user.email],
                    fail_silently=False,
                )
            except Exception:
                # Avoid failing the API just because email provider is misconfigured.
                pass

        return Response(
            {"detail": "If the email exists, you will receive reset instructions shortly."},
            status=200,
        )


@method_decorator(csrf_exempt, name="dispatch")
class PasswordResetConfirmView(APIView):
    """
    Confirm password reset using uid + token.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        uid = request.data.get("uid")
        token = request.data.get("token")
        new_password = request.data.get("new_password")

        if not uid or not token or not new_password:
            return Response({"detail": "uid, token and new_password are required."}, status=400)

        try:
            uid_int = int(urlsafe_base64_decode(uid).decode("utf-8"))
        except Exception:
            return Response({"detail": "Invalid uid."}, status=400)

        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(pk=uid_int)
        except UserModel.DoesNotExist:
            return Response({"detail": "Invalid user."}, status=400)

        if not default_token_generator.check_token(user, token):
            return Response({"detail": "Invalid or expired token."}, status=400)

        # Validate password using Django validators (if any)
        try:
            validate_password(new_password, user)
        except Exception as e:
            return Response({"detail": str(e)}, status=400)

        user.set_password(new_password)
        user.save()

        return Response({"detail": "Password reset successful."}, status=200)


@method_decorator(csrf_exempt, name="dispatch")
class ParentSelfProfileView(APIView):
    """Parent: read/update contact fields stored on ParentProfile + display name on User."""

    permission_classes = [permissions.IsAuthenticated, IsParentUser]

    def get(self, request):
        pp = parent_profile_for_user(request.user)
        if not pp:
            return Response({"detail": "Parent profile not found"}, status=404)
        f = pp.franchise
        return Response(
            {
                "id": request.user.id,
                "email": request.user.email,
                "full_name": request.user.full_name or "",
                "phone": pp.phone or "",
                "address": pp.address or "",
                "city": pp.city or "",
                "photo_url": pp.photo_url or "",
                "franchise_name": f.name,
                "franchise_contact_phone": f.contact_phone or "",
                "franchise_contact_email": f.contact_email or "",
                "notifications_muted": bool(pp.notifications_muted),
            }
        )

    def patch(self, request):
        user = request.user
        pp = parent_profile_for_user(user)
        if not pp:
            return Response({"detail": "Parent profile not found"}, status=404)

        full_name = request.data.get("full_name")
        if full_name is not None:
            user.full_name = str(full_name)[:255]
            user.save(update_fields=["full_name"])

        if "phone" in request.data:
            pp.phone = str(request.data.get("phone") or "")[:30]
        if "address" in request.data:
            pp.address = str(request.data.get("address") or "")
        if "city" in request.data:
            pp.city = str(request.data.get("city") or "")[:100]
        if "photo_url" in request.data:
            pp.photo_url = str(request.data.get("photo_url") or "")[:500]
        if "notifications_muted" in request.data:
            pp.notifications_muted = bool(request.data.get("notifications_muted"))
        pp.save()
        return self.get(request)
