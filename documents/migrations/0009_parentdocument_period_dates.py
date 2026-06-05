from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0008_alter_parentdocument_category_newsletter_label"),
    ]

    operations = [
        migrations.AddField(
            model_name="parentdocument",
            name="period_start",
            field=models.DateField(blank=True, help_text="Newsletter academic block start date", null=True),
        ),
        migrations.AddField(
            model_name="parentdocument",
            name="period_end",
            field=models.DateField(blank=True, help_text="Newsletter academic block end date", null=True),
        ),
    ]
