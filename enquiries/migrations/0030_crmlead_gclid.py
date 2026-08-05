from urllib.parse import parse_qs, urlparse

from django.db import migrations, models


def backfill_gclid_from_landing_url(apps, schema_editor):
    CrmLead = apps.get_model("enquiries", "CrmLead")
    for lead in CrmLead.objects.exclude(landing_page_url="").iterator(chunk_size=500):
        if (getattr(lead, "gclid", None) or "").strip():
            continue
        url = (lead.landing_page_url or "").strip()
        if "gclid=" not in url.lower():
            continue
        try:
            qs = parse_qs(urlparse(url).query)
            value = (qs.get("gclid") or [""])[0]
        except Exception:
            value = ""
        value = str(value or "").strip()[:255]
        if value:
            lead.gclid = value
            lead.save(update_fields=["gclid"])


class Migration(migrations.Migration):

    dependencies = [
        ("enquiries", "0029_crmlead_referral_sources"),
    ]

    operations = [
        migrations.AddField(
            model_name="crmlead",
            name="gclid",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Google Ads click ID (gclid) from the landing URL.",
                max_length=255,
            ),
        ),
        migrations.AddIndex(
            model_name="crmlead",
            index=models.Index(fields=["gclid"], name="idx_campaign_leads_gclid"),
        ),
        migrations.RunPython(backfill_gclid_from_landing_url, migrations.RunPython.noop),
    ]
