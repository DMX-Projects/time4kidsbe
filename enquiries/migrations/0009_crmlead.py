from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("enquiries", "0008_otpverification"),
    ]

    operations = [
        migrations.CreateModel(
            name="CrmLead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("full_name", models.CharField(max_length=255)),
                ("mobile", models.CharField(max_length=20)),
                ("email", models.EmailField(blank=True, default="", max_length=254)),
                ("state", models.CharField(blank=True, default="", max_length=100)),
                ("city", models.CharField(blank=True, default="", max_length=100)),
                ("preferred_centre_location", models.CharField(blank=True, default="", max_length=255)),
                ("franchise_type", models.CharField(blank=True, default="", max_length=100)),
                ("investment_range", models.CharField(blank=True, default="", max_length=100)),
                ("expected_start_date", models.CharField(blank=True, default="", max_length=100)),
                ("comments", models.TextField(blank=True, default="")),
                (
                    "source",
                    models.CharField(
                        choices=[("web", "Website"), ("fb", "Facebook"), ("insta", "Instagram")],
                        default="web",
                        max_length=20,
                    ),
                ),
                ("landing_page_url", models.URLField(blank=True, default="", max_length=500)),
                ("utm_source", models.CharField(blank=True, default="", max_length=150)),
                ("utm_medium", models.CharField(blank=True, default="", max_length=150)),
                ("utm_campaign", models.CharField(blank=True, default="", max_length=150)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("new", "New"),
                            ("contacted", "Contacted"),
                            ("follow_up", "Follow Up"),
                            ("interested", "Interested"),
                            ("meeting_scheduled", "Meeting Scheduled"),
                            ("converted", "Converted"),
                            ("dropped", "Dropped"),
                        ],
                        default="new",
                        max_length=30,
                    ),
                ),
                ("raw_payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "crm_leads",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="crmlead",
            index=models.Index(fields=["created_at"], name="idx_crm_leads_created_at"),
        ),
        migrations.AddIndex(
            model_name="crmlead",
            index=models.Index(fields=["source"], name="idx_crm_leads_source"),
        ),
        migrations.AddIndex(
            model_name="crmlead",
            index=models.Index(fields=["status"], name="idx_crm_leads_status"),
        ),
        migrations.AddIndex(
            model_name="crmlead",
            index=models.Index(fields=["mobile"], name="idx_crm_leads_mobile"),
        ),
    ]
