from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("enquiries", "0028_meeting_fixed_done"),
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
                    ("july_lp", "Google"),
                    ("july_meta", "META"),
                    ("lp_wb", "Google"),
                    ("franchise_referral", "Referral-Franchise"),
                    ("franchise_friends_family", "Referral - Friends & Family"),
                    ("referral_parents", "Referral - Parents"),
                    ("referral_family_friends", "Referral - Family & Friends"),
                ],
                default="web",
                max_length=40,
            ),
        ),
    ]
