import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "time4kids_be.settings")
django.setup()

from enquiries.crm_api import unified_reports_data

class FakeRequest:
    def __init__(self, query_params):
        self.query_params = query_params

# Retrieve reports for Hyderabad with source=admission for 2026
request = FakeRequest({
    "startDate": "2026-01-01T00:00:00.000Z",
    "endDate": "2026-12-31T23:59:59.999Z",
    "city": "Hyderabad",
    "source": "admission"
})

response_data = unified_reports_data(request)
print("Reports response data:")
print(response_data)
