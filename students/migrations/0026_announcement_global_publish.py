from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0025_franchise_notification"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="announcement",
            name="ho_admin",
            field=models.ForeignKey(
                blank=True,
                help_text="Head office admin who published this global notification.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="ho_announcements",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="announcement",
            name="publish_scope",
            field=models.CharField(
                blank=True,
                default="",
                help_text="pan_india, state, city, franchises, or one_centre when franchise is null.",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="announcement",
            name="target_cities",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="announcement",
            name="target_franchise_ids",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="announcement",
            name="target_states",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="announcement",
            name="visible_to_centres",
            field=models.BooleanField(
                default=True,
                help_text="When true, matching franchise centres see this in their notifications inbox.",
            ),
        ),
        migrations.AddField(
            model_name="announcement",
            name="visible_to_parents",
            field=models.BooleanField(
                default=True,
                help_text="When true, parents at matching centres see this in the parent app.",
            ),
        ),
        migrations.AlterField(
            model_name="announcement",
            name="franchise",
            field=models.ForeignKey(
                blank=True,
                help_text="Null for head-office global notifications with publish targeting.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="portal_announcements",
                to="franchises.franchise",
            ),
        ),
    ]
