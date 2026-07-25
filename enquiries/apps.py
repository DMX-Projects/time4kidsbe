from django.apps import AppConfig


class EnquiriesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "enquiries"

    def ready(self):
        # Hands-off Meta Lead Ads → CRM polling while webhooks are Pending.
        try:
            from .meta_leads_autosync import start_meta_leads_autosync

            start_meta_leads_autosync()
        except Exception:
            import logging

            logging.getLogger(__name__).exception("Failed to start Meta leads auto-sync")
