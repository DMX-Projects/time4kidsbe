from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0017_parentdocument_video_file"),
    ]

    operations = [
        migrations.AddField(
            model_name="parentdocument",
            name="publish_scope",
            field=models.CharField(
                blank=True,
                default="pan_india",
                help_text="Who sees this when franchise is blank: pan_india, state, city, franchises, one_centre.",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="parentdocument",
            name="target_cities",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="City names when publish_scope is city.",
            ),
        ),
        migrations.AddField(
            model_name="parentdocument",
            name="target_class_names",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Optional class labels for class-specific parent-app content.",
            ),
        ),
        migrations.AddField(
            model_name="parentdocument",
            name="target_franchise_ids",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Centre IDs when publish_scope is franchises or one_centre.",
            ),
        ),
        migrations.AddField(
            model_name="parentdocument",
            name="target_states",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="State codes (AP, TS, …) when publish_scope is state.",
            ),
        ),
    ]
