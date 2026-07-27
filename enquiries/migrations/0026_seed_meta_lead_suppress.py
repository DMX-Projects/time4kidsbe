# Seed meta_lead_suppress from existing Meta Instant Form CRM rows.

from django.db import migrations


def seed_suppress_from_existing_leads(apps, schema_editor):
    CrmLead = apps.get_model("enquiries", "CrmLead")
    MetaLeadSuppress = apps.get_model("enquiries", "MetaLeadSuppress")
    for lead in CrmLead.objects.iterator():
        payload = lead.raw_payload if isinstance(lead.raw_payload, dict) else {}
        leadgen_id = str(payload.get("meta_leadgen_id") or "").strip()
        if not leadgen_id:
            continue
        MetaLeadSuppress.objects.update_or_create(
            leadgen_id=leadgen_id,
            defaults={
                "form_id": str(payload.get("meta_form_id") or "")[:64],
                "form_name": str(payload.get("meta_form_name") or "")[:255],
                "crm_lead_id": lead.pk,
            },
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("enquiries", "0025_meta_lead_suppress"),
    ]

    operations = [
        migrations.RunPython(seed_suppress_from_existing_leads, noop_reverse),
    ]
