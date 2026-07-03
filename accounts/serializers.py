import os
import re

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.hashers import check_password
from django.db.models import Q
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from accounts.profile_access import parent_login_context, driver_profile_for_user, parent_profile_for_user

from .models import User, UserRole


def _normalize_phone10(identifier: str) -> str | None:
    digits = re.sub(r"\D", "", (identifier or "").strip())
    if len(digits) >= 10:
        return digits[-10:]
    return None


def _users_for_phone_login(phone10: str) -> list[User]:
    """ParentProfile.phone, DriverProfile.phone, or legacy student Mobileno."""
    from franchises.models import DriverProfile, ParentProfile
    from students.models import StudentProfile

    users: list[User] = []
    seen: set[int] = set()

    def add(user: User | None) -> None:
        if user and user.pk not in seen:
            seen.add(user.pk)
            users.append(user)

    for profile in ParentProfile.objects.filter(phone=phone10).select_related("user"):
        add(profile.user)

    for profile in DriverProfile.objects.filter(phone=phone10).select_related("user"):
        add(profile.user)

    for student in StudentProfile.objects.filter(Mobileno__icontains=phone10).select_related("parent__user"):
        if student.parent_id and student.parent.user_id:
            add(student.parent.user)

    return users


def _inactive_user_with_valid_password(identifier: str, password: str) -> User | None:
    """
    Django's ModelBackend.authenticate() returns None for inactive users even when the
    password is correct. Detect that so we can return a clear error instead of "Invalid credentials".
    """
    ident = (identifier or "").strip()
    if not ident or not password:
        return None
    candidates: list[User] = []
    seen: set[int] = set()

    def add(user: User | None) -> None:
        if user and user.pk not in seen:
            seen.add(user.pk)
            candidates.append(user)

    add(User.objects.filter(Q(email__iexact=ident) | Q(username__iexact=ident)).first())
    phone10 = _normalize_phone10(ident)
    if phone10:
        for user in _users_for_phone_login(phone10):
            add(user)

    for cand in candidates:
        if cand and not cand.is_active and cand.password:
            try:
                if cand.check_password(password):
                    return cand
            except Exception:  # noqa: BLE001
                continue
    return None


def _login_trace_enabled() -> bool:
    """Set ``DJANGO_LOGIN_TRACE=1`` (or ``settings.LOGIN_DEBUG_TRACE=True``) for login diagnostics."""
    if os.environ.get("DJANGO_LOGIN_TRACE", "").lower() in ("1", "true", "yes"):
        return True
    return bool(getattr(settings, "LOGIN_DEBUG_TRACE", False))


def _authenticate_with_identifier(identifier: str, password: str):
    """
    Resolve login identifier to a User and verify password.

    Django's ``authenticate()`` only accepts ``username=`` and ``password=`` for
    ``ModelBackend``; the value for ``username`` must match ``User.USERNAME_FIELD``
    (here: **email**). Never call ``authenticate(email=..., password=...)``.

    Flow:
    1. ``authenticate(username=ident, ...)`` when ``ident`` is the exact stored email.
    2. Find by ``email__iexact``, then ``authenticate(username=user.email, ...)``.
    3. Find by ``username__iexact`` (e.g. legacy id card in ``users.username``), then
       ``authenticate(username=user.email, ...)`` — password is checked against
       ``users.password`` only; ``username`` on the row is used for lookup only.
    4. Find by mobile (10-digit) on parent/driver profile or legacy student ``Mobileno``.
    """
    ident = (identifier or "").strip()
    if not ident or not password:
        return None

    if _login_trace_enabled():
        print(
            "LOGIN TRACE: identifier=%r password_len=%s"
            % (ident, len(password)),
            flush=True,
        )

    user = authenticate(username=ident, password=password)
    if _login_trace_enabled():
        print(
            "LOGIN TRACE: authenticate(username=ident, ...) ->",
            f"User(pk={user.pk})" if user else None,
            flush=True,
        )
    if user:
        return user

    by_email = User.objects.filter(email__iexact=ident).first()
    if by_email:
        user = authenticate(username=by_email.email, password=password)
        if _login_trace_enabled():
            print(
                "LOGIN TRACE: via email__iexact -> authenticate(username=%r, ...) ->"
                % (by_email.email,),
                f"User(pk={user.pk})" if user else None,
                flush=True,
            )
        if user:
            return user

    by_username = User.objects.filter(username__iexact=ident).first()
    if by_username:
        if _login_trace_enabled():
            raw_hash = by_username.password or ""
            print(
                "LOGIN TRACE: FOUND USER pk=%s username=%r email=%r"
                % (by_username.pk, by_username.username, by_username.email),
                flush=True,
            )
            print(
                "LOGIN TRACE: HASH prefix=%r"
                % (raw_hash[:48] + ("..." if len(raw_hash) > 48 else ""),),
                flush=True,
            )
            print(
                "LOGIN TRACE: hash start pbkdf2_sha256$=%s pbkdf2_=%s"
                % (raw_hash.startswith("pbkdf2_sha256$"), raw_hash.startswith("pbkdf2_")),
                flush=True,
            )
            print(
                "LOGIN TRACE: check_password(plain, user.password) ->",
                check_password(password, raw_hash),
                flush=True,
            )
            try:
                from students.models import StudentProfile

                sp = StudentProfile.objects.filter(Idcardno__iexact=ident).first()
                if sp:
                    print(
                        "LOGIN TRACE: StudentProfile.Idcardno=%r user.username=%r"
                        % (sp.Idcardno, by_username.username),
                        flush=True,
                    )
                else:
                    print(
                        "LOGIN TRACE: no StudentProfile with Idcardno__iexact=%r" % (ident,),
                        flush=True,
                    )
            except Exception as exc:  # pragma: no cover
                print("LOGIN TRACE: StudentProfile lookup:", exc, flush=True)

        user = authenticate(username=by_username.email, password=password)
        if _login_trace_enabled():
            print(
                "LOGIN TRACE: authenticate(username=user.email, ...) ->",
                f"User(pk={user.pk})" if user else None,
                flush=True,
            )
        if user:
            return user

    phone10 = _normalize_phone10(ident)
    if phone10:
        for cand in _users_for_phone_login(phone10):
            user = authenticate(username=cand.email, password=password)
            if _login_trace_enabled():
                print(
                    "LOGIN TRACE: via phone %r -> user pk=%s authenticate -> %s"
                    % (phone10, cand.pk, f"User(pk={user.pk})" if user else None),
                    flush=True,
                )
            if user:
                return user

    return None


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "username", "full_name", "role", "is_active"]
        read_only_fields = ["id", "role", "is_active"]


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = "email"

    def validate(self, attrs):
        # Accept either email or username as login identifier
        identifier = attrs.get("email")  # Field name is "email" but can contain username
        password = attrs.get("password")

        user = _authenticate_with_identifier(identifier, password) if identifier else None

        if not user:
            if _inactive_user_with_valid_password(identifier or "", password or ""):
                raise AuthenticationFailed("User account is disabled")
            raise AuthenticationFailed("Invalid credentials")
        if not user.is_active:
            raise AuthenticationFailed("User account is disabled")

        if user.normalized_role() == UserRole.CRM.value:
            raise PermissionDenied(
                "CRM accounts must sign in from the CRM login page (/crm-admin/login), not the main website login."
            )

        # We've authenticated the user manually.
        # SimpleJWT TokenObtainPairSerializer uses self.user to generate tokens.
        self.user = user

        # Generate tokens manually instead of calling super().validate(attrs)
        # to avoid the parent's authenticate() call which might fail with email= keyword
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user)

        data = {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

        if user.normalized_role() == UserRole.DRIVER.value:
            dp = driver_profile_for_user(user)
            if not dp:
                raise AuthenticationFailed(
                    "Driver profile not found. Ask your centre to create your driver account again."
                )
            from franchises.serializers import DriverProfileSerializer

            data["driver_profile"] = DriverProfileSerializer(
                dp,
                context={"request": self.context.get("request")},
            ).data
            return data

        data["user"] = {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
        }
        if user.normalized_role() == UserRole.PARENT.value:
            data["user"].update(parent_login_context(user))
        return data


class SimpleUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "password", "role"]
        read_only_fields = ["id"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        role = validated_data.get("role", UserRole.PARENT)
        user = User.objects.create_user(password=password, role=role, **validated_data)
        return user


class ParentTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Serializer for parent login - validates PARENT role and includes parent profile"""

    username_field = "email"

    def validate(self, attrs):
        # Accept either email or username as login identifier
        identifier = attrs.get("email")
        password = attrs.get("password")

        user = _authenticate_with_identifier(identifier, password) if identifier else None

        if not user:
            if _inactive_user_with_valid_password(identifier or "", password or ""):
                raise AuthenticationFailed("User account is disabled")
            raise AuthenticationFailed("Invalid credentials")

        if not user.is_active:
            raise AuthenticationFailed("User account is disabled")

        # Validate that user is a PARENT (legacy imports may store lowercase role)
        if user.normalized_role() != UserRole.PARENT.value:
            raise PermissionDenied(
                "This endpoint is only for parent accounts. "
                "Centre/franchise and admin users should sign in from the main login page "
                "(not the parent login link)."
            )

        # We've authenticated the user manually.
        self.user = user

        # Generate tokens manually
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user)

        data = {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

        parent_ctx = parent_login_context(user)

        data["user"] = {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            **parent_ctx,
        }

        return data


class CrmTokenObtainPairSerializer(TokenObtainPairSerializer):
    """CRM-only login — same email/password flow as timekids_crm_clone admin login."""

    username_field = "email"

    def validate(self, attrs):
        identifier = attrs.get("email")
        password = attrs.get("password")

        user = _authenticate_with_identifier(identifier, password) if identifier else None

        if not user:
            if _inactive_user_with_valid_password(identifier or "", password or ""):
                raise AuthenticationFailed("User account is disabled")
            raise AuthenticationFailed("Invalid credentials")

        if not user.is_active:
            raise AuthenticationFailed("User account is disabled")

        if user.normalized_role() != UserRole.CRM.value:
            raise PermissionDenied(
                "This login is for CRM accounts only. Use the main website login for admin, centre, or parent users."
            )

        self.user = user

        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
            },
        }
