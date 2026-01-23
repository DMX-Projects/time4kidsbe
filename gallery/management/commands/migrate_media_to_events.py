"""
Migration script to copy MediaItem data to EventMedia for gallery display.

This script migrates media from the old gallery.MediaItem model to the new
events.EventMedia model, associating them with appropriate Event objects.
"""

from django.core.management.base import BaseCommand
from gallery.models import MediaItem
from events.models import Event, EventMedia
from franchises.models import Franchise
from datetime import date


class Command(BaseCommand):
    help = 'Migrate MediaItem records to EventMedia under appropriate Events'

    def handle(self, *args, **options):
        # Get all media items
        media_items = MediaItem.objects.all()
        
        if not media_items.exists():
            self.stdout.write(self.style.WARNING('No MediaItem records found to migrate'))
            return

        migrated_count = 0
        
        for media_item in media_items:
            # For each franchise, ensure there's a "General" event or create one
            # Since MediaItem doesn't have franchise FK, we'll create events for each franchise
            # and associate all media items with them
            
            # Option 1: Create a single event per franchise for all migrated media
            # Option 2: Ask user which franchise to associate
            
            # For now, let's find the first active franchise or create a general one
            franchise = Franchise.objects.filter(is_active=True).first()
            
            if not franchise:
                self.stdout.write(self.style.ERROR('No active franchise found. Please create a franchise first.'))
                return
            
            # Check if a "General Media" event exists for this franchise
            event, created = Event.objects.get_or_create(
                franchise=franchise,
                title=f"{media_item.category}" if media_item.category else "General",
                defaults={
                    'description': f'Migrated from old gallery system - {media_item.category}',
                    'start_date': media_item.created_at.date() if media_item.created_at else date.today(),
                }
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created Event: {event.title}'))
            
            # Map media_type from old format to new format
            media_type_mapping = {
                'image': EventMedia.MediaType.IMAGE,
                'video': EventMedia.MediaType.VIDEO,
            }
            
            # Create EventMedia from MediaItem
            event_media, created = EventMedia.objects.get_or_create(
                event=event,
                file=media_item.file,
                defaults={
                    'media_type': media_type_mapping.get(media_item.media_type, EventMedia.MediaType.IMAGE),
                    'caption': media_item.title,
                }
            )
            
            if created:
                migrated_count += 1
                self.stdout.write(self.style.SUCCESS(
                    f'✓ Migrated: {media_item.title} → Event: {event.title}'
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f'⊘ Already exists: {media_item.title}'
                ))
        
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Migration complete! Migrated {migrated_count} media items.'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'💡 Tip: Check your franchise gallery at /locations/[city]/[school]/#gallery'
        ))
