from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("enquiries", "0021_rename_crm_leads_to_campaign_leads"),
    ]

    operations = [
        migrations.AlterField(
            model_name="crmlead",
            name="source",
            field=models.CharField(
                choices=[
                    ("web", "Website"),
                    ("fb", "Facebook"),
                    ("insta", "Instagram"),
                    ("july_lp", "LP July"),
                    ("july_meta", "Meta July"),
                    ("lp_wb", "LP-WB"),
                ],
                default="web",
                max_length=20,
            ),
        ),
    ]
