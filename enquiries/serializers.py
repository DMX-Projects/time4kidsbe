from rest_framework import serializers

from accounts.registration_checks import ALREADY_REGISTERED_MESSAGE, email_has_parent_account
from franchises.models import Franchise

from .models import CrmLead, Enquiry, EnquiryType, FranchiseEnquiry, KidsEnquiry


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
            "meeting_date",
            "next_follow_up_date",
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

    def validate(self, attrs):
        attrs = super().validate(attrs)
        enquiry_type = attrs.get("enquiry_type")
        if enquiry_type == EnquiryType.ADMISSION or enquiry_type == "ADMISSION":
            email = (attrs.get("email") or "").strip().lower()
            if email_has_parent_account(email):
                raise serializers.ValidationError({"email": ALREADY_REGISTERED_MESSAGE})
        return attrs

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
            "state",
            "city",
            "child_age",
            "franchise",
            "franchise_name",
            "status",
            "meeting_date",
            "next_follow_up_date",
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
            "state",
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
        fields = ["name", "email", "phone", "message", "state", "city"]

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
        fields = ["status", "meeting_date", "next_follow_up_date"]


class KidsEnquirySerializer(serializers.ModelSerializer):
    """Same columns as ``public.kids_enquiry`` — no extra fields."""

    class Meta:
        model = KidsEnquiry
        fields = [
            "id",
            "name",
            "mobile",
            "mobileno",
            "email",
            "state",
            "city",
            "location",
            "enquiry_type",
            "created_date",
            "source",
            "centre_name",
            "centre_phone",
            "centre_email",
            "email_status",
            "whatsapp_status",
            "raw_payload",
        ]
        read_only_fields = fields


class CrmLeadSerializer(serializers.ModelSerializer):
    """CRM leads stored separately from landing leads and enquiries."""

    fullName = serializers.CharField(source="full_name", required=False, allow_blank=True, write_only=True)
    preferredCentreLocation = serializers.CharField(
        source="preferred_centre_location", required=False, allow_blank=True, write_only=True
    )
    franchiseType = serializers.CharField(source="franchise_type", required=False, allow_blank=True, write_only=True)
    investmentRange = serializers.CharField(source="investment_range", required=False, allow_blank=True, write_only=True)
    expectedStartDate = serializers.CharField(source="expected_start_date", required=False, allow_blank=True, write_only=True)
    landingPageUrl = serializers.CharField(source="landing_page_url", required=False, allow_blank=True, write_only=True)
    utmSource = serializers.CharField(source="utm_source", required=False, allow_blank=True, write_only=True)
    utmMedium = serializers.CharField(source="utm_medium", required=False, allow_blank=True, write_only=True)
    utmCampaign = serializers.CharField(source="utm_campaign", required=False, allow_blank=True, write_only=True)

    class Meta:
        model = CrmLead
        fields = [
            "id",
            "full_name",
            "fullName",
            "mobile",
            "email",
            "state",
            "city",
            "preferred_centre_location",
            "preferredCentreLocation",
            "franchise_type",
            "franchiseType",
            "investment_range",
            "investmentRange",
            "expected_start_date",
            "expectedStartDate",
            "comments",
            "source",
            "landing_page_url",
            "landingPageUrl",
            "utm_source",
            "utmSource",
            "utm_medium",
            "utmMedium",
            "utm_campaign",
            "utmCampaign",
            "status",
            "raw_payload",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "raw_payload", "created_at", "updated_at"]
        extra_kwargs = {
            "full_name": {"required": False, "allow_blank": True},
            "email": {"required": False, "allow_blank": True},
            "state": {"required": False, "allow_blank": True},
            "city": {"required": False, "allow_blank": True},
            "preferred_centre_location": {"required": False, "allow_blank": True},
            "franchise_type": {"required": False, "allow_blank": True},
            "investment_range": {"required": False, "allow_blank": True},
            "expected_start_date": {"required": False, "allow_blank": True},
            "comments": {"required": False, "allow_blank": True},
            "landing_page_url": {"required": False, "allow_blank": True},
            "utm_source": {"required": False, "allow_blank": True},
            "utm_medium": {"required": False, "allow_blank": True},
            "utm_campaign": {"required": False, "allow_blank": True},
        }

    def validate(self, attrs):
        attrs = super().validate(attrs)
        full_name = (attrs.get("full_name") or "").strip()
        mobile = (attrs.get("mobile") or "").strip()
        if not full_name:
            raise serializers.ValidationError({"full_name": "Name is required."})
        if not mobile:
            raise serializers.ValidationError({"mobile": "Mobile number is required."})
        attrs["full_name"] = full_name
        attrs["mobile"] = mobile
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        if request is not None:
            validated_data["raw_payload"] = getattr(request, "data", {}) or {}
        return super().create(validated_data)
