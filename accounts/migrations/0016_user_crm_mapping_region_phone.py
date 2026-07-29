# Generated manually — sheet-shaped CRM columns: mapping region + phone

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0015_user_crm_designation_full_state_names"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="crm_mapping_region",
            field=models.CharField(
                blank=True,
                default="",
                help_text="CRM only: region label from mapping sheet (e.g. AP/TS, Kerala, TN/KL/MH).",
                max_length=120,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="crm_phone",
            field=models.CharField(
                blank=True,
                default="",
                help_text="CRM only: team member mobile/phone from mapping sheet.",
                max_length=20,
            ),
        ),
    ]
