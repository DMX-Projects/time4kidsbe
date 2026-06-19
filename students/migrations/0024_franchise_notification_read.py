from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("franchises", "0001_initial"),
        ("students", "0023_announcement_campaign"),
    ]

    operations = [
        migrations.CreateModel(
            name="FranchiseNotificationRead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("notification_key", models.CharField(max_length=120)),
                ("read_at", models.DateTimeField(auto_now_add=True)),
                (
                    "franchise",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inbox_reads",
                        to="franchises.franchise",
                    ),
                ),
            ],
            options={
                "ordering": ["-read_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="franchisenotificationread",
            constraint=models.UniqueConstraint(
                fields=("franchise", "notification_key"),
                name="uniq_franchise_notification_key",
            ),
        ),
    ]
