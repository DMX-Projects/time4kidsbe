from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('enquiries', '0031_crmlead_other_channel_sources'),
    ]

    operations = [
        migrations.AlterField(
            model_name='crmlead',
            name='source',
            field=models.CharField(choices=[('web', 'Website'), ('fb', 'Facebook'), ('insta', 'Instagram'), ('july_lp', 'Google'), ('july_meta', 'META'), ('lp_wb', 'Google'), ('franchise_referral', 'Referral-Franchise'), ('franchise_friends_family', 'Referral - Friends & Family'), ('referral_parents', 'Referral - Parents'), ('referral_family_friends', 'Referral - Family & Friends'), ('whatsapp', 'WhatsApp'), ('sms', 'SMS'), ('email', 'Email'), ('admission_whatsapp', 'WhatsApp (Admission)'), ('admission_sms', 'SMS (Admission)'), ('admission_email', 'Email (Admission)'), ('franchise_website', 'Website Leads'), ('campaign_google', 'Paid Campaign - Google'), ('campaign_meta', 'Paid Campaign - META'), ('youtube', 'Paid Campaign - YouTube'), ('admission_website', 'Website (Admission)'), ('admission_google', 'Paid Campaign - Google (Admission)'), ('admission_meta', 'Paid Campaign - META (Admission)'), ('admission_youtube', 'Paid Campaign - YouTube (Admission)')], default='web', max_length=40),
        ),
    ]
