from rest_framework import serializers
from .models import Update

class UpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Update
        fields = ['id', 'franchise', 'text', 'start_date', 'end_date', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['franchise']
