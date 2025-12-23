from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

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
            # Try authenticating with email
            user = authenticate(email=identifier, password=password)
            
            # If email auth fails, try to find user by username and authenticate
            if not user:
                try:
                    from .models import User
                    user_obj = User.objects.filter(username=identifier).first()
                    if user_obj:
                        user = authenticate(email=user_obj.email, password=password)
                except:
                    pass
        
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        if not user.is_active:
            raise serializers.ValidationError("User account is disabled")
        
        # Call parent validate with email to generate tokens
        attrs["email"] = user.email
        data = super().validate(attrs)
        data["user"] = {
            "id": self.user.id,
            "email": self.user.email,
            "full_name": self.user.full_name,
            "role": self.user.role,
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
