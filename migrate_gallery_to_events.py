"""
Migration script to convert FranchiseGalleryItem to Event and EventMedia models.

This script groups gallery items by franchise, event_category, and academic_year,
creates Event objects for each unique combination, and converts each gallery item
into an EventMedia record.

Usage:
    python migrate_gallery_to_events.py [--dry-run]
"""

import os
import sys
import django
from datetime import datetime
from django.db import transaction

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'time4kids_be.settings')
django.setup()

from franchises.models import FranchiseGalleryItem, Franchise
from events.models import Event, EventMedia


def parse_academic_year(academic_year_str):
    """Parse academic year string like '2023-24' to get start year."""
    try:
        if '-' in academic_year_str:
            year = int(academic_year_str.split('-')[0])
        else:
            year = int(academic_year_str)
        return year
    except (ValueError, AttributeError):
        return datetime.now().year


def migrate_gallery_to_events(dry_run=False):
    """Main migration function."""
    
    print("=" * 80)
    print("FRANCHISE GALLERY ITEM to EVENT MIGRATION")
    print("=" * 80)
    print()
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made to the database\n")
    
    # Get all gallery items grouped by franchise
    gallery_items = FranchiseGalleryItem.objects.all().select_related('franchise')
    total_items = gallery_items.count()
    
    if total_items == 0:
        print("ℹ️  No gallery items found to migrate.")
        return
    
    print(f"📊 Found {total_items} gallery items to migrate\n")
    
    # Group items by (franchise, event_category, academic_year)
    events_to_create = {}
    
    for item in gallery_items:
        key = (item.franchise.id, item.event_category, item.academic_year)
        if key not in events_to_create:
            events_to_create[key] = {
                'franchise': item.franchise,
                'event_category': item.event_category,
                'academic_year': item.academic_year,
                'items': []
            }
        events_to_create[key]['items'].append(item)
    
    print(f"📦 Will create {len(events_to_create)} events from gallery items\n")
    print("-" * 80)
    
    events_created = 0
    media_created = 0
    errors = []
    
    try:
        with transaction.atomic():
            for (franchise_id, event_category, academic_year), data in events_to_create.items():
                franchise = data['franchise']
                items = data['items']
                
                # Parse academic year to get start date
                year = parse_academic_year(academic_year)
                # Use July 1st as a reasonable start date for academic year events
                start_date = datetime(year, 7, 1).date()
                
                print(f"\n📌 Franchise: {franchise.name}")
                print(f"   Event: {event_category}")
                print(f"   Academic Year: {academic_year}")
                print(f"   Items to migrate: {len(items)}")
                
                if not dry_run:
                    # Create or get event
                    event, created = Event.objects.get_or_create(
                        franchise=franchise,
                        title=event_category,
                        start_date=start_date,
                        defaults={
                            'description': f"{event_category} - {academic_year}",
                            'location': franchise.city or '',
                        }
                    )
                    
                    if created:
                        events_created += 1
                        print(f"   ✅ Created event: {event.title}")
                    else:
                        print(f"   ℹ️  Event already exists: {event.title}")
                    
                    # Migrate each gallery item to EventMedia
                    for item in items:
                        try:
                            # Determine media type
                            if item.media_type == 'video':
                                media_type = EventMedia.MediaType.VIDEO
                            else:
                                media_type = EventMedia.MediaType.IMAGE
                            
                            # Create EventMedia
                            event_media = EventMedia.objects.create(
                                event=event,
                                file=item.image,  # Reuse the uploaded file
                                media_type=media_type,
                                caption=item.title,
                                uploaded_by=None,  # Could be set to franchise user if available
                            )
                            media_created += 1
                            print(f"      ➕ Migrated: {item.title} ({item.media_type})")
                            
                        except Exception as e:
                            error_msg = f"Error migrating item {item.id} ({item.title}): {str(e)}"
                            errors.append(error_msg)
                            print(f"      ❌ {error_msg}")
                else:
                    print(f"   [DRY RUN] Would create event and migrate {len(items)} items")
                    events_created += 1 if dry_run else 0
                    media_created += len(items)
            
            if dry_run:
                # Rollback transaction in dry run mode
                raise Exception("Dry run - rolling back transaction")
                
    except Exception as e:
        if not dry_run:
            print(f"\n❌ Migration failed: {str(e)}")
            raise
        else:
            # Expected in dry run mode
            pass
    
    print("\n" + "=" * 80)
    print("MIGRATION SUMMARY")
    print("=" * 80)
    print(f"✅ Events created: {events_created}")
    print(f"✅ Media items created: {media_created}")
    if errors:
        print(f"\n⚠️  Errors encountered: {len(errors)}")
        for error in errors:
            print(f"   - {error}")
    
    if dry_run:
        print("\n🔍 DRY RUN COMPLETE - No actual changes were made")
    else:
        print("\n✅ MIGRATION COMPLETE!")
        print("\n💡 Next steps:")
        print("   1. Verify the migrated events in the admin panel")
        print("   2. Update the frontend to use the new event-based gallery")
        print("   3. Once verified, you can safely delete old FranchiseGalleryItem records")


if __name__ == '__main__':
    # Check for dry-run flag
    dry_run = '--dry-run' in sys.argv
    
    try:
        migrate_gallery_to_events(dry_run=dry_run)
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {str(e)}")
        sys.exit(1)
