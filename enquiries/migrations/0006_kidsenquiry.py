from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("enquiries", "0005_franchiseenquiry_split"),
    ]

    operations = [
        migrations.CreateModel(
            name="KidsEnquiry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.TextField()),
                ("mobile", models.TextField(blank=True, null=True)),
                ("mobileno", models.TextField()),
                ("email", models.TextField(blank=True, null=True)),
                ("state", models.TextField(blank=True, null=True)),
                ("city", models.TextField(blank=True, null=True)),
                ("location", models.TextField(blank=True, null=True)),
                ("enquiry_type", models.TextField()),
                ("created_date", models.DateTimeField(auto_now_add=True)),
                ("source", models.TextField(blank=True, null=True)),
                ("centre_name", models.TextField(blank=True, null=True)),
                ("centre_phone", models.TextField(blank=True, null=True)),
                ("centre_email", models.TextField(blank=True, null=True)),
                ("email_status", models.TextField(blank=True, null=True)),
                ("whatsapp_status", models.TextField(blank=True, null=True)),
                ("raw_payload", models.JSONField(default=dict)),
            ],
            options={
                "db_table": "kids_enquiry",
                "ordering": ["-created_date"],
            },
        ),
    ]
