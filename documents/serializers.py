from rest_framework import serializers
from .models import ParentDocument
from common.fields import RelativeFileField, RelativeImageField


class ParentDocumentSerializer(serializers.ModelSerializer):
    file = RelativeFileField()
    thumbnail = RelativeImageField(required=False, allow_null=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    franchise_name = serializers.CharField(source='franchise.name', read_only=True, allow_null=True)
    state_display = serializers.CharField(source='get_state_display', read_only=True, allow_null=True)
    display_title = serializers.SerializerMethodField()

    class Meta:
        model = ParentDocument
        fields = ['id', 'category', 'category_display', 'title', 'description', 
                  'file', 'thumbnail', 'franchise', 'franchise_name', 'is_active', 
                  'order', 'state', 'state_display', 'academic_year', 'display_title',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_display_title(self, obj):
        """Return formatted title - for holiday lists, include state and academic year"""
        if obj.category == 'HOLIDAY_LISTS':
            if obj.title:
                return f"{obj.title} ({obj.academic_year})" if obj.academic_year else obj.title
            state_display = obj.get_state_display() if obj.state else ''
            year = f" ({obj.academic_year})" if obj.academic_year else ''
            return f"{state_display}{year}" if state_display else obj.title
        return obj.title

