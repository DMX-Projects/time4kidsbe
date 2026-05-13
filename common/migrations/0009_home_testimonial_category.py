from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("common", "0008_marketingasset_pagecontent"),
    ]

    operations = [
        migrations.AddField(
            model_name="hometestimonial",
            name="category",
            field=models.CharField(
                choices=[
                    ("parent", "Parent"),
                    ("franchisee", "Franchisee"),
                ],
                default="parent",
                max_length=20,
            ),
        ),
    ]
