from rest_framework import serializers

from .models import Career, JobApplication


class CareerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Career
        fields = [
            "id",
            "title",
            "department",
            "type",
            "description",
            "location",
            "apply_email",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class JobApplicationSerializer(serializers.ModelSerializer):
    career_title = serializers.CharField(source='career.title', read_only=True)
    
    class Meta:
        model = JobApplication
        fields = [
            "id",
            "career",
            "career_title",
            "full_name",
            "email",
            "phone",
            "linkedin_url",
            "resume",
            "cover_letter",
            "status",
            "applied_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "applied_at", "updated_at"]

    def validate_resume(self, value):
        """Validate resume file size and type"""
        # Max file size: 5MB
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Resume file size cannot exceed 5MB.")
        
        # Accepted file types
        allowed_extensions = ['.pdf', '.doc', '.docx']
        import os
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in allowed_extensions:
            raise serializers.ValidationError(
                f"Unsupported file type. Please upload PDF, DOC, or DOCX files only."
            )
        
        return value
