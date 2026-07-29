import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("enquiries", "0026_seed_meta_lead_suppress"),
    ]

    operations = [
        migrations.AddField(
            model_name="kidsenquiry",
            name="assigned_user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assigned_landing_leads",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
