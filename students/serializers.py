from rest_framework import serializers
from .models import StudentProfile, Grade
from common.fields import RelativeImageField


class GradeSerializer(serializers.ModelSerializer):
    percentage = serializers.ReadOnlyField()

    class Meta:
        model = Grade
        fields = ['id', 'subject', 'exam_type', 'marks_obtained', 'total_marks', 
                  'grade', 'percentage', 'exam_date', 'remarks', 'created_at']
        read_only_fields = ['id', 'created_at']


class StudentProfileSerializer(serializers.ModelSerializer):
    profile_picture = RelativeImageField(required=False, allow_null=True)
    full_name = serializers.ReadOnlyField()
    parent_info = serializers.SerializerMethodField()
    grades_count = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = ['id', 'first_name', 'last_name', 'full_name', 'class_name', 
                  'roll_number', 'date_of_birth', 'admission_date', 'profile_picture',
                  'is_active', 'parent_info', 'grades_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_parent_info(self, obj):
        return {
            'id': obj.parent.id,
            'parent_name': obj.parent.user.full_name,
            'franchise_name': obj.parent.franchise.name
        }

    def get_grades_count(self, obj):
        return obj.grades.count()


class StudentDetailSerializer(StudentProfileSerializer):
    """Extended serializer with grades"""
    grades = GradeSerializer(many=True, read_only=True)

    class Meta(StudentProfileSerializer.Meta):
        fields = StudentProfileSerializer.Meta.fields + ['grades']

