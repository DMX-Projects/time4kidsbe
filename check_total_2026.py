import os
import django
from django.db.models import Q

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "time4kids_be.settings")
django.setup()

from enquiries.models import Enquiry, CrmLead, FranchiseEnquiry

start_date = "2026-01-01 00:00:00"
end_date = "2026-12-31 23:59:59"

print("--- 2026 Enquiries (Enquiry model) ---")
enq_all = Enquiry.objects.filter(created_at__range=(start_date, end_date))
print(f"Total Enquiry records: {enq_all.count()}")
print(f"  Admission/general: {enq_all.filter(enquiry_type__in=['ADMISSION', 'general']).count()}")
print(f"  Contact: {enq_all.filter(enquiry_type='CONTACT').count()}")

print("\n--- 2026 CrmLeads (CrmLead model) ---")
crm_all = CrmLead.objects.filter(created_at__range=(start_date, end_date))
print(f"Total CrmLead records: {crm_all.count()}")

print("\n--- 2026 FranchiseEnquiries ---")
fe_all = FranchiseEnquiry.objects.filter(created_at__range=(start_date, end_date))
print(f"Total FranchiseEnquiry records: {fe_all.count()}")

grand_total = enq_all.count() + crm_all.count() + fe_all.count()
print(f"\nGRAND TOTAL of all CRM tables for 2026: {grand_total}")
