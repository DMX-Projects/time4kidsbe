import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'time4kids_be.settings')
django.setup()

from accounts.models import User, UserRole
from franchises.models import Franchise

email = "banashankari5thstage@timekidspreschools.com"
password = "hello@123"

# Create or Update User
print(f"Checking user: {email}...")
user, created = User.objects.get_or_create(
    email=email,
    defaults={
        'full_name': 'Banashankari 5th Stage Demo',
        'role': UserRole.FRANCHISE
    }
)

if created:
    print(f"Created new user: {email}")
else:
    print(f"User found: {email}")

# Always set password to ensure it matches
user.set_password(password)
user.role = UserRole.FRANCHISE  # Ensure role is correct
user.save()
print(f"Password set to: {password}")

# Ensure Franchise Profile Exists
franchise, f_created = Franchise.objects.get_or_create(
    user=user,
    defaults={
        'admin': user,
        'name': 'Banashankari 5th Stage Franchise',
        'city': 'Bangalore',
        'contact_email': email,
        'slug': 'banashankari-5th-stage'
    }
)

if f_created:
    print(f"Created Franchise profile: {franchise.name}")
else:
    print(f"Existing Franchise profile confirmed: {franchise.name}")

print("\n--- Setup Complete ---")
print("You can now login with these credentials.")
