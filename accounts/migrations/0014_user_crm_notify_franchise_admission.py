# Generated manually for franchise vs admission notify flags

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0013_user_crm_notify_leads"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="crm_notify_franchise",
            field=models.BooleanField(
                default=False,
                help_text="Receive new-lead emails for Franchise leads in this territory.",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="crm_notify_admission",
            field=models.BooleanField(
                default=False,
                help_text="Receive new-lead emails for Admission leads in this territory.",
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="crm_notify_leads",
            field=models.BooleanField(
                default=False,
                help_text="Deprecated: use crm_notify_franchise / crm_notify_admission.",
            ),
        ),
    ]
