from rest_framework import serializers

from franchises.models import Franchise

from franchises.models import Franchise

from .models import Enquiry, FranchiseEnquiry, FranchiseEnquiry


class EnquirySerializer(serializers.ModelSerializer):
    franchise_slug = serializers.CharField(write_only=True, required=False, allow_blank=True)
    franchise_name = serializers.CharField(read_only=True, source="franchise.name")
    record_source = serializers.SerializerMethodField(read_only=True)

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
            "record_source",
        ]
        read_only_fields = ["id", "franchise", "created_at", "record_source"]

    def get_record_source(self, obj: Enquiry) -> str:
        return "enquiry"

    def validate_enquiry_type(self, value: str) -> str:
        if value == "FRANCHISE":
            raise serializers.ValidationError(
                "Franchise opportunity leads use POST /enquiries/franchise-submit/."
            )
        return value

    def create(self, validated_data):
        franchise_slug = validated_data.pop("franchise_slug", None)
        city = validated_data.get("city", "").strip()

        if franchise_slug:
            franchise = Franchise.objects.filter(slug=franchise_slug).first()
            if franchise:
                validated_data["franchise"] = franchise
                return Enquiry.objects.create(**validated_data)

        global_data = validated_data.copy()
        global_data["franchise"] = None
        global_enquiry = Enquiry.objects.create(**global_data)

        if city:
            city_query = city.lower()
            if city_query in ["banglore", "bangalore"]:
                city_query = "bengaluru"

            validated_data["city"] = city_query
            global_data["city"] = city_query
            global_enquiry.city = city_query
            global_enquiry.save()

            franchises = Franchise.objects.filter(city__iexact=city_query)
            for franchise in franchises:
                data = validated_data.copy()
                data["franchise"] = franchise
                Enquiry.objects.create(**data)

        return global_enquiry


class FranchiseEnquiryReadSerializer(serializers.ModelSerializer):
    """Expose franchise leads using the same JSON shape as `Enquiry` list rows."""

    enquiry_type = serializers.SerializerMethodField()
    child_age = serializers.SerializerMethodField()
    franchise_name = serializers.CharField(read_only=True, source="franchise.name")
    record_source = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = FranchiseEnquiry
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
            "franchise_name",
            "status",
            "created_at",
            "record_source",
        ]
        read_only_fields = [
            "id",
            "enquiry_type",
            "name",
            "email",
            "phone",
            "message",
            "city",
            "child_age",
            "franchise",
            "franchise_name",
            "status",
            "created_at",
            "record_source",
        ]

    def get_enquiry_type(self, obj: FranchiseEnquiry) -> str:
        return "FRANCHISE"

    def get_child_age(self, obj: FranchiseEnquiry) -> str:
        return ""

    def get_record_source(self, obj: FranchiseEnquiry) -> str:
        return "franchise_enquiry"


class FranchiseEnquiryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FranchiseEnquiry
        fields = ["name", "email", "phone", "message", "city"]

    def create(self, validated_data):
        city = validated_data.get("city", "").strip()

        global_data = validated_data.copy()
        global_data["franchise"] = None
        global_row = FranchiseEnquiry.objects.create(**global_data)

        if city:
            city_query = city.lower()
            if city_query in ["banglore", "bangalore"]:
                city_query = "bengaluru"

            validated_data["city"] = city_query
            global_data["city"] = city_query
            global_row.city = city_query
            global_row.save()

            franchises = Franchise.objects.filter(city__iexact=city_query)
            for franchise in franchises:
                data = validated_data.copy()
                data["franchise"] = franchise
                FranchiseEnquiry.objects.create(**data)

        return global_row


class FranchiseEnquiryStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = FranchiseEnquiry
        fields = ["status"]
