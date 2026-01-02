from rest_framework import serializers
from .models import HeroSlide
from .fields import RelativeImageField

class HeroSlideSerializer(serializers.ModelSerializer):
    image = RelativeImageField()
    mobile_image = RelativeImageField(required=False, allow_null=True)

    class Meta:
        model = HeroSlide
        fields = '__all__'
