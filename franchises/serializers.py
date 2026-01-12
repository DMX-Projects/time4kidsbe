from django.utils.text import slugify
from rest_framework import serializers

from accounts.models import User, UserRole
from accounts.serializers import UserSerializer
from events.serializers import EventSerializer
from .models import Franchise, ParentProfile, FranchiseLocation
from common.fields import RelativeImageField


class FranchiseLocationSerializer(serializers.ModelSerializer):
    """Serializer for franchise location data."""
    state_display = serializers.CharField(source='get_state_display', read_only=True)
    
    class Meta:
        model = FranchiseLocation
        fields = ['id', 'city_name', 'state', 'state_display', 'is_active', 'display_order']
        read_only_fields = ['id', 'state_display']


class FranchiseSerializer(serializers.ModelSerializer):
    admin = UserSerializer(read_only=True)
    user = UserSerializer(read_only=True)
    hero_image = RelativeImageField(required=False, allow_null=True)

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
            "facebook_url",
            "instagram_url",
            "twitter_url",
            "linkedin_url",
            "youtube_url",
            "programs",
            "facilities",
            "hero_image",
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

    def validate(self, attrs):
        required_fields = [
            "name",
            "city",
            "contact_email",
            "contact_phone",
        ]
        missing = [f for f in required_fields if not attrs.get(f)]
        if missing:
            raise serializers.ValidationError({"detail": f"Missing required fields: {', '.join(missing)}"})
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
    class Meta(FranchiseSerializer.Meta):
        read_only_fields = ["id", "slug", "created_at", "updated_at", "admin", "user", "is_active"]


class ParentSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True, min_length=8)
    full_name = serializers.CharField(write_only=True)

    class Meta:
        model = ParentProfile
        fields = ["id", "user", "email", "full_name", "password", "franchise", "child_name", "notes", "created_at"]
        read_only_fields = ["id", "user", "franchise", "created_at"]

    def create(self, validated_data):
        email = validated_data.pop("email")
        password = validated_data.pop("password")
        full_name = validated_data.pop("full_name")
        franchise = self.context.get("franchise")
        user = User.objects.create_user(email=email, password=password, full_name=full_name, role=UserRole.PARENT)
        parent = ParentProfile.objects.create(user=user, franchise=franchise, **validated_data)
        return parent


class PublicFranchiseSerializer(serializers.ModelSerializer):
    events = EventSerializer(many=True, read_only=True)

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
            "facebook_url",
            "instagram_url",
            "twitter_url",
            "linkedin_url",
            "youtube_url",
            "programs",
            "facilities",
            "hero_image",
            "events",
        ]
        read_only_fields = fields
