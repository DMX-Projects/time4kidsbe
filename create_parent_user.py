#!/usr/bin/env python
"""Script to create a parent user with login credentials"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'time4kids_be.settings')
django.setup()

from accounts.models import User, UserRole
from franchises.models import Franchise, ParentProfile

# Check if there are any franchises
franchises = Franchise.objects.all()
if not franchises.exists():
    print("No franchises found. Creating a test franchise first...")
    # Create an admin user for the franchise
    admin_email = "admin@time4kids.com"
    admin_user = User.objects.filter(email=admin_email).first()
    if not admin_user:
        admin_user = User.objects.create_superuser(
            email=admin_email,
            password="admin123",
            full_name="Admin User"
        )
        print(f"Created admin user: {admin_email} / admin123")
    
    # Create franchise user
    franchise_email = "franchise@time4kids.com"
    franchise_user = User.objects.filter(email=franchise_email).first()
    if not franchise_user:
        franchise_user = User.objects.create_user(
            email=franchise_email,
            password="franchise123",
            full_name="Franchise User",
            role=UserRole.FRANCHISE
        )
        print(f"Created franchise user: {franchise_email} / franchise123")
    
    # Create franchise
    franchise = Franchise.objects.create(
        admin=admin_user,
        user=franchise_user,
        name="Time4Kids Mumbai",
        slug="time4kids-mumbai",
        city="Mumbai",
        state="Maharashtra",
        contact_email=franchise_email,
        contact_phone="+91-9876543210"
    )
    print(f"Created franchise: {franchise.name}")
else:
    franchise = franchises.first()
    print(f"Using existing franchise: {franchise.name}")

# Create parent user
parent_email = "parent@time4kids.com"
parent_password = "parent123"

# Check if parent user already exists
parent_user = User.objects.filter(email=parent_email).first()
if parent_user:
    print(f"Parent user already exists: {parent_email}")
    if not hasattr(parent_user, 'parent_profile'):
        # Create parent profile if missing
        ParentProfile.objects.create(
            user=parent_user,
            franchise=franchise,
            child_name="Test Child"
        )
        print("Created parent profile for existing user")
else:
    # Create new parent user
    parent_user = User.objects.create_user(
        email=parent_email,
        password=parent_password,
        full_name="John Doe",
        role=UserRole.PARENT
    )
    print(f"Created parent user: {parent_email}")
    
    # Create parent profile
    parent_profile = ParentProfile.objects.create(
        user=parent_user,
        franchise=franchise,
        child_name="Jane Doe"
    )
    print(f"Created parent profile for: {parent_profile.user.full_name}")

    print("\n" + "="*50)
    print("PARENT LOGIN CREDENTIALS")
    print("="*50)
    print(f"Email: {parent_email}")
    print(f"Password: {parent_password}")
    print(f"Full Name: {parent_user.full_name}")
    print(f"Child Name: {parent_user.parent_profile.child_name}")
    print(f"Franchise: {franchise.name}")
    print("="*50)

