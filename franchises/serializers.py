import re

from django.db import IntegrityError, transaction
from django.utils.text import slugify
from rest_framework import serializers

from accounts.models import User, UserRole
from accounts.serializers import UserSerializer
from events.serializers import EventSerializer
from .models import DriverProfile, Franchise, ParentProfile, FranchiseLocation, FranchiseHeroSlide, FranchiseGalleryItem
from common.fields import RelativeFileField, RelativeImageField


# ... (FranchiseLocationSerializer, FranchiseSerializer, FranchiseCreateSerializer, FranchiseUpdateSerializer, FranchiseProfileSerializer, ParentSerializer, FranchiseHeroSlideSerializer remain unchanged) ...

class FranchiseGalleryItemSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(default=True)

    class Meta:
        model = FranchiseGalleryItem
        fields = ["id", "media_type", "title", "image", "video_link", "academic_year", "event_category", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        if attrs.get('media_type') == 'video' and not attrs.get('video_link'):
             raise serializers.ValidationError({"video_link": "Video link is required for video items."})
        return attrs


class PublicFranchiseSerializer(serializers.ModelSerializer):
    events = EventSerializer(many=True, read_only=True)
    hero_slides = serializers.SerializerMethodField()
    gallery_items = serializers.SerializerMethodField()

    class Meta:
        model = Franchise
        fields = [
            "id",
            "name",
            "slug",
            "about",
            "address",
            "city",
            "state",
            "country",
            "postal_code",
            "contact_email",
            "contact_phone",
            "google_map_link",
            "latitude",
            "longitude",
            "facebook_url",
            "instagram_url",
            "twitter_url",
            "linkedin_url",
            "youtube_url",
            "programs",
            "facilities",
            "hero_image",
            "school_program_cards",
            "events",
            "hero_slides",
            "gallery_items",
        ]
        read_only_fields = fields

    def get_hero_slides(self, obj):
        slides = obj.hero_slides.filter(is_active=True).order_by('order', '-created_at')
        return FranchiseHeroSlideSerializer(slides, many=True).data

    def get_gallery_items(self, obj):
        items = obj.gallery_items.filter(is_active=True).order_by('-created_at')
        return FranchiseGalleryItemSerializer(items, many=True).data


class FranchiseLocationSerializer(serializers.ModelSerializer):
    """Serializer for franchise location data."""
    state_display = serializers.CharField(source='get_state_display', read_only=True)
    
    class Meta:
        model = FranchiseLocation
        fields = ['id', 'city_name', 'state', 'state_display', 'is_active', 'display_order']
        read_only_fields = ['id', 'state_display']


class FranchiseSerializer(serializers.ModelSerializer):
    admin = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()
    hero_image = RelativeImageField(required=False, allow_null=True)

    def get_admin(self, obj: Franchise):
        if not obj.admin_id:
            return None
        try:
            return UserSerializer(obj.admin).data
        except User.DoesNotExist:
            return {
                "id": obj.admin_id,
                "email": "",
                "username": None,
                "full_name": f"(missing user #{obj.admin_id})",
                "role": None,
                "is_active": False,
            }

    def get_user(self, obj: Franchise):
        if not obj.user_id:
            return None
        try:
            return UserSerializer(obj.user).data
        except User.DoesNotExist:
            return {
                "id": obj.user_id,
                "email": "",
                "username": None,
                "full_name": f"(missing user #{obj.user_id})",
                "role": None,
                "is_active": False,
            }

    class Meta:
        model = Franchise
        fields = [
            "id",
            "name",
            "slug",
            "about",
            "address",
            "city",
            "state",
            "country",
            "postal_code",
            "contact_email",
            "contact_phone",
            "google_map_link",
            "latitude",
            "longitude",
            "facebook_url",
            "instagram_url",
            "twitter_url",
            "linkedin_url",
            "youtube_url",
            "programs",
            "facilities",
            "hero_image",
            "school_program_cards",
            "created_at",
            "updated_at",
            "is_active",
            "admin",
            "user",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at", "admin", "user"]
        extra_kwargs = {
            "name": {"required": True},
            "address": {"required": False},
            "city": {"required": True},
            "state": {"required": False},
            "country": {"required": False},
            "contact_email": {"required": True},
            "contact_phone": {"required": True},
        }


class FranchiseCreateSerializer(FranchiseSerializer):
    franchise_email = serializers.EmailField(write_only=True)
    franchise_password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    franchise_full_name = serializers.CharField(write_only=True)

    class Meta(FranchiseSerializer.Meta):
        fields = FranchiseSerializer.Meta.fields + [
            "franchise_email",
            "franchise_password",
            "franchise_full_name",
        ]
        extra_kwargs = {
            **FranchiseSerializer.Meta.extra_kwargs,
            "city": {"required": False, "allow_blank": True},
            "contact_email": {"required": False, "allow_blank": True},
            "contact_phone": {"required": False, "allow_blank": True},
        }

    def validate(self, attrs):
        for key in list(attrs.keys()):
            val = attrs.get(key)
            if isinstance(val, str):
                attrs[key] = val.strip()
        if not attrs.get("name"):
            raise serializers.ValidationError({"name": "This field is required."})
        if not attrs.get("franchise_full_name"):
            raise serializers.ValidationError({"franchise_full_name": "This field is required."})
        if not attrs.get("contact_email"):
            attrs["contact_email"] = attrs.get("franchise_email") or ""
        if attrs.get("contact_phone") is None:
            attrs["contact_phone"] = ""
        if not attrs.get("city"):
            attrs["city"] = ""
        return attrs

    def create(self, validated_data):
        franchise_email = validated_data.pop("franchise_email")
        
        # Check if user already exists
        if User.objects.filter(email=franchise_email).exists():
            raise serializers.ValidationError({"franchise_email": "A user with this email already exists."})

        franchise_password = validated_data.pop("franchise_password", None) or franchise_email
        franchise_full_name = validated_data.pop("franchise_full_name")
        
        # Get admin from validated_data (injected by perform_create) or context
        admin_user = validated_data.pop("admin", None)
        if not admin_user:
            request = self.context.get("request")
            admin_user = request.user if request else None
        if not admin_user or not getattr(admin_user, "pk", None):
            raise serializers.ValidationError(
                {"detail": "An authenticated admin user is required to create a franchise."}
            )

        user = User.objects.create_user(
            email=franchise_email,
            password=franchise_password,
            full_name=franchise_full_name,
            role=UserRole.FRANCHISE,
        )
        if not validated_data.get("contact_email"):
            validated_data["contact_email"] = franchise_email

        base_slug = slugify(validated_data.get("slug") or validated_data.get("name", franchise_full_name))
        slug = base_slug or slugify(franchise_email)
        counter = 1
        while Franchise.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}" if base_slug else f"franchise-{counter}"
            counter += 1
        validated_data["slug"] = slug
        
        # Ensure optional fields have defaults if missing to prevent IntegrityError
        optional_fields = [
            "address", "state", "country", "postal_code", "about", "programs", "facilities",
            "google_map_link", "facebook_url", "instagram_url", "twitter_url", "linkedin_url", "youtube_url"
        ]
        for field in optional_fields:
            if field not in validated_data:
                validated_data[field] = ""

        franchise = Franchise.objects.create(admin=admin_user, user=user, **validated_data)
        return franchise


class FranchiseUpdateSerializer(FranchiseSerializer):
    class Meta(FranchiseSerializer.Meta):
        read_only_fields = ["id", "slug", "created_at", "updated_at", "admin", "user"]


class FranchiseProfileSerializer(FranchiseSerializer):
    centre_access = serializers.SerializerMethodField()

    class Meta(FranchiseSerializer.Meta):
        read_only_fields = ["id", "slug", "created_at", "updated_at", "admin", "user", "is_active", "centre_access"]

    def get_centre_access(self, obj):
        from accounts.profile_access import franchise_centre_diagnostics

        request = self.context.get("request")
        user = getattr(request, "user", None)
        return franchise_centre_diagnostics(user)


class ParentListSerializer(serializers.ModelSerializer):
    """Light list payload for centre parent grid (avoids huge live responses)."""

    name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()

    class Meta:
        model = ParentProfile
        fields = ["id", "name", "email", "child_name", "phone", "notes", "Emailid", "created_at"]
        read_only_fields = fields

    def get_name(self, obj: ParentProfile) -> str:
        if not obj.user_id:
            return ""
        try:
            return (obj.user.full_name or "").strip() or obj.user.email
        except User.DoesNotExist:
            return obj.Emailid or ""

    def get_email(self, obj: ParentProfile) -> str:
        if not obj.user_id:
            return obj.Emailid or ""
        try:
            return obj.user.email or obj.Emailid or ""
        except User.DoesNotExist:
            return obj.Emailid or ""


class ParentSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    email = serializers.EmailField(write_only=True, required=False)
    password = serializers.CharField(write_only=True, min_length=8, required=False)
    full_name = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = ParentProfile
        fields = [
            "id",
            "user",
            "email",
            "full_name",
            "password",
            "franchise",
            "child_name",
            "phone",
            "notes",
            "Emailid",
            "created_at",
        ]
        read_only_fields = ["id", "user", "franchise", "created_at"]

    def get_user(self, obj: ParentProfile):
        if not obj.user_id:
            return None
        try:
            return UserSerializer(obj.user).data
        except User.DoesNotExist:
            return {
                "id": obj.user_id,
                "email": obj.Emailid or "",
                "username": None,
                "full_name": f"(missing user #{obj.user_id})",
                "role": None,
                "is_active": False,
            }

    def validate(self, attrs):
        if self.instance is None:
            if not (attrs.get("email") or "").strip():
                raise serializers.ValidationError({"email": "Email is required."})
            if not (attrs.get("password") or "").strip():
                raise serializers.ValidationError({"password": "Password is required (min 8 characters)."})
            if not (attrs.get("full_name") or "").strip():
                raise serializers.ValidationError({"full_name": "Parent name is required."})
        return attrs

    def create(self, validated_data):
        franchise = self.context.get("franchise")
        if franchise is None:
            raise serializers.ValidationError(
                {
                    "detail": "This login is not linked to a centre (franchise). "
                    "Use the centre/franchise login, or contact support to fix the account."
                }
            )

        email = validated_data.pop("email")
        password = validated_data.pop("password")
        full_name = validated_data.pop("full_name")

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    email=email, password=password, full_name=full_name, role=UserRole.PARENT
                )
                parent = ParentProfile.objects.create(user=user, franchise=franchise, **validated_data)
        except IntegrityError as exc:
            err = str(exc).lower()
            if "email" in err or "accounts_user_email" in err:
                raise serializers.ValidationError(
                    {"email": "An account with this email already exists. Use a different email or reset password."}
                ) from exc
            raise serializers.ValidationError(
                {"detail": "Could not create this parent record (duplicate or invalid data)."}
            ) from exc

        return parent

    def update(self, instance, validated_data):
        email = validated_data.pop("email", None)
        full_name = validated_data.pop("full_name", None)
        password = validated_data.pop("password", None)
        
        user_updated = False
        if email is not None and email != instance.user.email:
            # Basic duplicate check for email update
            if User.objects.filter(email=email).exclude(id=instance.user.id).exists():
                raise serializers.ValidationError({"email": "An account with this email already exists."})
            instance.user.email = email
            instance.user.username = email
            user_updated = True
            
        if full_name is not None:
            instance.user.full_name = full_name
            user_updated = True
            
        if password:
            instance.user.set_password(password)
            user_updated = True
            
        if user_updated:
            instance.user.save()

        return super().update(instance, validated_data)


class DriverProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    license_document = RelativeFileField(read_only=True)
    vehicle_rc = RelativeFileField(read_only=True)
    vehicle_insurance = RelativeFileField(read_only=True)

    class Meta:
        model = DriverProfile
        fields = [
            "id",
            "user",
            "phone",
            "service_number",
            "license_number",
            "license_document",
            "vehicle_rc",
            "vehicle_insurance",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "user", "created_at"]


class DriverCreateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True, min_length=8)
    full_name = serializers.CharField(write_only=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    service_number = serializers.CharField(required=False, allow_blank=True)
    license_number = serializers.CharField(required=False, allow_blank=True)
    license_document = RelativeFileField(required=False, allow_null=True)
    vehicle_rc = RelativeFileField(required=False, allow_null=True)
    vehicle_insurance = RelativeFileField(required=False, allow_null=True)

    class Meta:
        model = DriverProfile
        fields = [
            "id",
            "email",
            "password",
            "full_name",
            "phone",
            "service_number",
            "license_number",
            "license_document",
            "vehicle_rc",
            "vehicle_insurance",
        ]

    def validate_phone(self, value):
        if not value:
            return ""
        digits = re.sub(r"\D", "", value)
        if len(digits) != 10:
            raise serializers.ValidationError("Phone number must be exactly 10 digits.")
        return digits

    def create(self, validated_data):
        # Always pop to avoid duplicate arguments, check context first as primary source
        val_franchise = validated_data.pop("franchise", None)
        franchise = self.context.get("franchise") or val_franchise
        if not franchise:
            raise serializers.ValidationError({"detail": "Franchise context is required."})

        email = validated_data.pop("email")
        password = validated_data.pop("password")
        full_name = validated_data.pop("full_name")

        try:
            with transaction.atomic():
                existing = User.objects.filter(email__iexact=email).first()
                if existing:
                    if existing.normalized_role() != UserRole.DRIVER.value:
                        raise serializers.ValidationError(
                            {"email": "An account with this email already exists with a different role."}
                        )
                    if DriverProfile.objects.filter(user_id=existing.pk).exists():
                        raise serializers.ValidationError(
                            {"email": "A driver account with this email already exists."}
                        )
                    existing.full_name = full_name
                    existing.set_password(password)
                    existing.role = UserRole.DRIVER
                    existing.username = existing.username or email
                    existing.save(update_fields=["full_name", "password", "role", "username"])
                    user = existing
                else:
                    user = User.objects.create_user(
                        email=email,
                        username=email,
                        password=password,
                        full_name=full_name,
                        role=UserRole.DRIVER,
                    )
                driver = DriverProfile.objects.create(user=user, franchise=franchise, **validated_data)
                return driver
        except IntegrityError:
            raise serializers.ValidationError({"email": "User with this email or username already exists."})
        except serializers.ValidationError:
            raise
        except Exception as e:
            raise serializers.ValidationError({"detail": f"An unexpected error occurred: {str(e)}"})


class FranchiseHeroSlideSerializer(serializers.ModelSerializer):
    """Use RelativeImageField so missing/corrupt files on disk do not 500 list/detail JSON."""

    is_active = serializers.BooleanField(default=True)
    image = RelativeImageField()

    class Meta:
        model = FranchiseHeroSlide
        fields = ["id", "image", "alt_text", "link", "order", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        # Automatically assign the franchise from the context (user's franchise)
        return super().create(validated_data)


class CityOptionSerializer(serializers.Serializer):
    """Distinct ``franchise.city`` value for the city dropdown."""

    name = serializers.CharField()


class CentreOptionSerializer(serializers.ModelSerializer):
    """Centre row from ``franchise`` (``name`` + slug for enquiry submission)."""

    class Meta:
        model = Franchise
        fields = ["id", "name", "slug"]


