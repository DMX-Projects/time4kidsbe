import os
import sys
import django

# Add the project root to sys.path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'time4kids_be.settings')
django.setup()

from enquiries.models import Enquiry
from enquiries.serializers import EnquirySerializer
from franchises.models import Franchise

def test_slug_submission():
    f = Franchise.objects.first()
    if not f:
        print("No franchise found to test with.")
        return

    print(f"Testing with franchise: {f.name} ({f.slug})")
    
    # Test Data simulating a direct school submission
    data = {
        'name': 'Slug Logic Test',
        'email': 'logic_test@example.com',
        'phone': '9876543210',
        'message': 'Testing visibility',
        'franchise_slug': f.slug,
        'enquiry_type': 'ADMISSION' # ensure type is set
    }
    
    serializer = EnquirySerializer(data=data)
    if serializer.is_valid():
        enquiry = serializer.save()
        print(f"✅ Enquiry Created: ID {enquiry.id}")
        print(f"   -> Linked Franchise: {enquiry.franchise}")
        
        # Verify if a global record was created (should be 0)
        global_count = Enquiry.objects.filter(email='logic_test@example.com', franchise__isnull=True).count()
        print(f"   -> Global Records (Admin View): {global_count}")
        
        if global_count == 0:
            print("SUCCESS: Direct submission is hidden from Admin (Active Filter: franchise__isnull=True)")
        else:
            print("FAILURE: Global record was still created!")
    else:
        print("Serializer Errors:", serializer.errors)

if __name__ == "__main__":
    test_slug_submission()
