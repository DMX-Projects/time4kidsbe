"""Head-office notification campaigns — resolve centres and sync delivery rows."""

from __future__ import annotations

from django.db.models import Q

from franchises.models import Franchise

from .models import Announcement, AnnouncementCampaign

INDIAN_STATE_CODE_TO_NAME = {
    "AP": "Andhra Pradesh",
    "AR": "Arunachal Pradesh",
    "AS": "Assam",
    "BR": "Bihar",
    "CG": "Chhattisgarh",
    "GA": "Goa",
    "GJ": "Gujarat",
    "HR": "Haryana",
    "HP": "Himachal Pradesh",
    "JH": "Jharkhand",
    "KA": "Karnataka",
    "KL": "Kerala",
    "MP": "Madhya Pradesh",
    "MH": "Maharashtra",
    "MN": "Manipur",
    "ML": "Meghalaya",
    "MZ": "Mizoram",
    "NL": "Nagaland",
    "OD": "Odisha",
    "PB": "Punjab",
    "RJ": "Rajasthan",
    "SK": "Sikkim",
    "TN": "Tamil Nadu",
    "TS": "Telangana",
    "TR": "Tripura",
    "UP": "Uttar Pradesh",
    "UK": "Uttarakhand",
    "WB": "West Bengal",
}


def publish_target_label(campaign: AnnouncementCampaign) -> str:
    scope = campaign.publish_scope or AnnouncementCampaign.PublishScope.PAN_INDIA
    if scope == AnnouncementCampaign.PublishScope.PAN_INDIA:
        return "Pan-India (all centres)"
    if scope == AnnouncementCampaign.PublishScope.ONE_CENTRE:
        if campaign.franchise_id:
            try:
                return campaign.franchise.name
            except Franchise.DoesNotExist:
                pass
        return "One centre"
    if scope == AnnouncementCampaign.PublishScope.FRANCHISES:
        count = len(campaign.target_franchise_ids or [])
        return f"{count} selected centre(s)"
    if scope == AnnouncementCampaign.PublishScope.STATE:
        labels = []
        for code in campaign.target_states or []:
            labels.append(INDIAN_STATE_CODE_TO_NAME.get(code, code))
        return f"States: {', '.join(labels) or '—'}"
    if scope == AnnouncementCampaign.PublishScope.CITY:
        cities = campaign.target_cities or []
        return f"Cities: {', '.join(cities) or '—'}"
    return "—"


def audience_label(campaign: AnnouncementCampaign) -> str:
    if campaign.student_id:
        try:
            name = campaign.student.full_name
            if name:
                return name
        except Exception:
            pass
        return f"Student #{campaign.student_id}"
    target_class = (campaign.class_name or "").strip()
    if target_class:
        return target_class
    return "All parents"


def resolve_franchises_for_campaign(campaign: AnnouncementCampaign) -> list[Franchise]:
    qs = Franchise.objects.filter(is_active=True)
    scope = campaign.publish_scope or AnnouncementCampaign.PublishScope.PAN_INDIA

    if scope == AnnouncementCampaign.PublishScope.PAN_INDIA:
        return list(qs.order_by("name"))

    if scope in (
        AnnouncementCampaign.PublishScope.ONE_CENTRE,
        AnnouncementCampaign.PublishScope.FRANCHISES,
    ):
        ids: list[int] = []
        if scope == AnnouncementCampaign.PublishScope.ONE_CENTRE and campaign.franchise_id:
            ids = [campaign.franchise_id]
        else:
            ids = [int(x) for x in (campaign.target_franchise_ids or []) if str(x).isdigit()]
        if not ids:
            return []
        return list(qs.filter(pk__in=ids).order_by("name"))

    if scope == AnnouncementCampaign.PublishScope.STATE:
        q = Q()
        for code in campaign.target_states or []:
            label = INDIAN_STATE_CODE_TO_NAME.get(code, code)
            q |= Q(state__iexact=label) | Q(statename__iexact=label) | Q(state__iexact=code)
        if not q:
            return []
        return list(qs.filter(q).distinct().order_by("name"))

    if scope == AnnouncementCampaign.PublishScope.CITY:
        q = Q()
        for city in campaign.target_cities or []:
            city = (city or "").strip()
            if not city:
                continue
            q |= Q(city__iexact=city) | Q(cityname__iexact=city)
        if not q:
            return []
        return list(qs.filter(q).distinct().order_by("name"))

    return []


def sync_campaign_deliveries(campaign: AnnouncementCampaign, *, after_save=None) -> None:
    """Create/update/delete per-centre Announcement rows for a campaign."""
    franchises = resolve_franchises_for_campaign(campaign)
    target_ids = {f.id for f in franchises}
    delivery_student = campaign.student if campaign.publish_scope == AnnouncementCampaign.PublishScope.ONE_CENTRE else None
    delivery_class = (campaign.class_name or "").strip()

    existing = {a.franchise_id: a for a in campaign.deliveries.select_related("franchise")}

    for franchise in franchises:
        fields = {
            "title": campaign.title,
            "body": campaign.body,
            "student": delivery_student,
            "class_name": delivery_class,
            "published_at": campaign.published_at,
            "is_active": campaign.is_active,
            "visible_to_parents": campaign.visible_to_parents,
            "visible_to_centres": campaign.visible_to_centres,
        }
        if franchise.id in existing:
            ann = existing[franchise.id]
            changed = any(getattr(ann, key) != val for key, val in fields.items())
            if changed:
                for key, val in fields.items():
                    setattr(ann, key, val)
                ann.save()
                if after_save:
                    after_save(ann)
        else:
            ann = Announcement.objects.create(campaign=campaign, franchise=franchise, **fields)
            if after_save:
                after_save(ann)

    campaign.deliveries.exclude(franchise_id__in=target_ids).delete()
