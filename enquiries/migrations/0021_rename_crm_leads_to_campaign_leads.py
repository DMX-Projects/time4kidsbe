# Generated manually: rename crm_leads → campaign_leads

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("enquiries", "0020_otpverification_is_verified"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelTable(
                    name="crmlead",
                    table="campaign_leads",
                ),
                migrations.AlterModelTable(
                    name="crmleadnote",
                    table="campaign_lead_notes",
                ),
                migrations.RenameIndex(
                    model_name="crmlead",
                    new_name="idx_campaign_leads_created_at",
                    old_name="idx_crm_leads_created_at",
                ),
                migrations.RenameIndex(
                    model_name="crmlead",
                    new_name="idx_campaign_leads_source",
                    old_name="idx_crm_leads_source",
                ),
                migrations.RenameIndex(
                    model_name="crmlead",
                    new_name="idx_campaign_leads_status",
                    old_name="idx_crm_leads_status",
                ),
                migrations.RenameIndex(
                    model_name="crmlead",
                    new_name="idx_campaign_leads_mobile",
                    old_name="idx_crm_leads_mobile",
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql='ALTER TABLE IF EXISTS "crm_leads" RENAME TO "campaign_leads";',
                    reverse_sql='ALTER TABLE IF EXISTS "campaign_leads" RENAME TO "crm_leads";',
                ),
                migrations.RunSQL(
                    sql='ALTER TABLE IF EXISTS "crm_lead_notes" RENAME TO "campaign_lead_notes";',
                    reverse_sql='ALTER TABLE IF EXISTS "campaign_lead_notes" RENAME TO "crm_lead_notes";',
                ),
                migrations.RunSQL(
                    sql='ALTER INDEX IF EXISTS "idx_crm_leads_created_at" RENAME TO "idx_campaign_leads_created_at";',
                    reverse_sql='ALTER INDEX IF EXISTS "idx_campaign_leads_created_at" RENAME TO "idx_crm_leads_created_at";',
                ),
                migrations.RunSQL(
                    sql='ALTER INDEX IF EXISTS "idx_crm_leads_source" RENAME TO "idx_campaign_leads_source";',
                    reverse_sql='ALTER INDEX IF EXISTS "idx_campaign_leads_source" RENAME TO "idx_crm_leads_source";',
                ),
                migrations.RunSQL(
                    sql='ALTER INDEX IF EXISTS "idx_crm_leads_status" RENAME TO "idx_campaign_leads_status";',
                    reverse_sql='ALTER INDEX IF EXISTS "idx_campaign_leads_status" RENAME TO "idx_crm_leads_status";',
                ),
                migrations.RunSQL(
                    sql='ALTER INDEX IF EXISTS "idx_crm_leads_mobile" RENAME TO "idx_campaign_leads_mobile";',
                    reverse_sql='ALTER INDEX IF EXISTS "idx_campaign_leads_mobile" RENAME TO "idx_crm_leads_mobile";',
                ),
            ],
        ),
    ]
