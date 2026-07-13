import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "time4kids_be.settings")
django.setup()

from enquiries.models import Enquiry

hyderabad_enquiries = Enquiry.objects.filter(city="Hyderabad").order_by("-created_at")
print(f"Total Hyderabad enquiries: {hyderabad_enquiries.count()}")
print("\nLatest 25 Hyderabad enquiries:")
for e in hyderabad_enquiries[:25]:
    print(f"ID: {e.id} | Type: {e.enquiry_type} | Status: {e.status} | Date: {e.created_at}")
