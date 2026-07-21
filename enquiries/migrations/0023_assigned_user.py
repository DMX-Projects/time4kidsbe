# Generated manually for assigned_user on CRM lead models

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("enquiries", "0022_crmleadsource_lp_wb"),
    ]

    operations = [
        migrations.AddField(
            model_name="crmlead",
            name="assigned_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assigned_campaign_leads",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="enquiry",
            name="assigned_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assigned_enquiries",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="franchiseenquiry",
            name="assigned_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assigned_franchise_enquiries",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
