from rest_framework import serializers
from .models import MediaItem
from common.fields import RelativeFileField

class MediaItemSerializer(serializers.ModelSerializer):
    file = RelativeFileField()

    class Meta:
        model = MediaItem
        fields = ['id', 'title', 'file', 'media_type', 'category', 'created_at']
