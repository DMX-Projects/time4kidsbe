from django.db import migrations


JOE_EMAIL = "joejoseph@timekidspreschools.com"
VIVEK_EMAIL = "vivek@timekidspreschools.com"
KERALA_SOUTH = "Ernakulam,Kottayam,Alappuzha,Kollam,Trivandrum,Pathanamthitta,Idukki"


def correct_kerala_crm_roles(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(email__iexact=JOE_EMAIL).update(crm_cities="")
    User.objects.filter(email__iexact=VIVEK_EMAIL).update(crm_designation="Manager")


def restore_kerala_crm_roles(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(email__iexact=JOE_EMAIL).update(crm_cities=KERALA_SOUTH)
    User.objects.filter(email__iexact=VIVEK_EMAIL).update(
        crm_designation="Regional Manager"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0016_user_crm_mapping_region_phone"),
    ]

    operations = [
        migrations.RunPython(
            correct_kerala_crm_roles,
            reverse_code=restore_kerala_crm_roles,
        ),
    ]
