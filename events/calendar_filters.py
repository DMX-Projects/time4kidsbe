"""Events used only as containers for parent-app Showcase uploads — not real school calendar items."""

from django.db.models import Q

# Must match franchise parent-portal ShowcaseTab auto-create payload.
SHOWCASE_PLACEHOLDER_DESCRIPTION = "Auto-created from Showcase upload"


def exclude_showcase_placeholder_events(qs):
    """Drop placeholder events created to hold Showcase media (parent portal)."""
    return qs.exclude(
        Q(location__iexact="Showcase") | Q(description=SHOWCASE_PLACEHOLDER_DESCRIPTION)
    )
