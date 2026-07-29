# Generated manually — crm_designation + longer crm_states for full names

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0014_user_crm_notify_franchise_admission"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="crm_designation",
            field=models.CharField(
                blank=True,
                default="",
                help_text="CRM only: designation from territory mapping sheet.",
                max_length=64,
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="crm_states",
            field=models.CharField(
                blank=True,
                default="",
                help_text='CRM only: comma-separated full state names (e.g. "Tamil Nadu, Kerala"). Overrides zone/region when set.',
                max_length=400,
            ),
        ),
    ]
