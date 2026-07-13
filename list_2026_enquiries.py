import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "time4kids_be.settings")
django.setup()

from enquiries.models import Enquiry

enqs_2026 = Enquiry.objects.filter(created_at__year=2026).order_by("created_at")
print(f"Total Enquiries in 2026: {enqs_2026.count()}")

print("\n--- Leads by Domain ---")
from django.db.models import Count
domains = enqs_2026.extra(select={'domain': 'SUBSTRING(email FROM POSITION(\'@\' IN email) + 1)'}).values('domain').annotate(count=Count('id')).order_by('-count')[:15]
for d in domains:
    print(f"Domain: {d['domain']} | Count: {d['count']}")

print("\n--- Potential duplicates (same name and email in 2026) ---")
dup_checks = enqs_2026.values("name", "email").annotate(count=Count("id")).filter(count__gt=1)
for dc in dup_checks:
    print(f"Duplicate Name: {dc['name']} | Email: {dc['email']} | Count: {dc['count']}")

print("\n--- Sample of the latest 20 leads ---")
for e in enqs_2026.order_by("-created_at")[:20]:
    print(f"Date: {e.created_at} | Name: {e.name} | City: {e.city} | Email: {e.email} | Type: {e.enquiry_type}")
