from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from accounts.profile_access import parent_profile_for_user

from .models import User, UserRole


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
        
        # Try to find user by email first, then by username
        user = None
        if identifier:
            # Try authenticating with email - ModelBackend expects 'username' keyword
            user = authenticate(username=identifier, password=password)
            
            # If email auth fails, try to find user by username and authenticate
            if not user:
                try:
                    user_obj = User.objects.filter(username=identifier).first()
                    if user_obj:
                        user = authenticate(username=user_obj.email, password=password)
                except:
                    pass
        
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        if not user.is_active:
            raise serializers.ValidationError("User account is disabled")
        
        # We've authenticated the user manually. 
        # SimpleJWT TokenObtainPairSerializer uses self.user to generate tokens.
        self.user = user
        
        # Generate tokens manually instead of calling super().validate(attrs)
        # to avoid the parent's authenticate() call which might fail with email= keyword
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        
        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
        
        data["user"] = {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
        }
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
        
        # Try to find user by email first, then by username
        user = None
        if identifier:
            # Try authenticating with email - ModelBackend expects 'username' keyword
            user = authenticate(username=identifier, password=password)
            
            # If email auth fails, try to find user by username and authenticate
            if not user:
                try:
                    user_obj = User.objects.filter(username=identifier).first()
                    if user_obj:
                        user = authenticate(username=user_obj.email, password=password)
                except:
                    pass
        
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        
        if not user.is_active:
            raise serializers.ValidationError("User account is disabled")
        
        # Validate that user is a PARENT
        if user.role != UserRole.PARENT:
            raise serializers.ValidationError("This login is only for parent accounts")
        
        # We've authenticated the user manually.
        self.user = user
        
        # Generate tokens manually
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        
        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
        
        parent_profile = parent_profile_for_user(user)
        
        data["user"] = {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
        }
        
        # Add parent profile information if available
        if parent_profile:
            data["parent_profile"] = {
                "id": parent_profile.id,
                "franchise_id": parent_profile.franchise.id,
                "franchise_name": parent_profile.franchise.name,
                "franchise_slug": parent_profile.franchise.slug,
                "child_name": parent_profile.child_name,
            }
        
        return data