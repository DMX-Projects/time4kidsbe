from rest_framework import serializers

from franchises.models import Franchise
from .models import Enquiry, EnquiryType


class EnquirySerializer(serializers.ModelSerializer):
    franchise_slug = serializers.CharField(write_only=True, required=False, allow_blank=True)
    franchise_name = serializers.CharField(read_only=True, source="franchise.name")

    class Meta:
        model = Enquiry
        fields = [
            "id",
            "enquiry_type",
            "name",
            "email",
            "phone",
            "message",
            "city",
            "child_age",
            "franchise",
            "franchise_slug",
            "franchise_name",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "franchise", "created_at"]

    # Validation removed to allow global admission enquiries


    def create(self, validated_data):
        franchise_slug = validated_data.pop("franchise_slug", None)
        city = validated_data.get("city", "").strip()
        
        
        # 1. Direct School Submission (Private to Franchise)
        # If a slug is provided, it means the user is on a specific school page.
        # User Requirement: These should NOT be visible to Admin.
        if franchise_slug:
            franchise = Franchise.objects.filter(slug=franchise_slug).first()
            if franchise:
                validated_data["franchise"] = franchise
                return Enquiry.objects.create(**validated_data)
        
        # 2. Main Website/City Submission (Visible to Admin + Relevant Franchises)
        # Create a Global Record first for Admin visibility (franchise=None)
        global_data = validated_data.copy()
        global_data["franchise"] = None
        global_enquiry = Enquiry.objects.create(**global_data)
        
        # Handle City-based duplication for Franchises
        if city:
            city_query = city.lower()
            if city_query in ["banglore", "bangalore"]:
                city_query = "bengaluru"
            
            # Update the data to be saved with the normalized city name
            validated_data["city"] = city_query
            global_data["city"] = city_query
            global_enquiry.city = city_query
            global_enquiry.save()

            franchises = Franchise.objects.filter(city__iexact=city_query)
            for franchise in franchises:
                data = validated_data.copy()
                data["franchise"] = franchise
                Enquiry.objects.create(**data)
        
        # Return the global enquiry to the API caller
        return global_enquiry
