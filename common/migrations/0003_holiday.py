# Generated manually for Holiday model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0002_heroslide_link'),
    ]

    operations = [
        migrations.CreateModel(
            name='Holiday',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state', models.CharField(choices=[('AP', 'Andhra Pradesh'), ('TS', 'Telangana'), ('KA', 'Karnataka'), ('KL', 'Kerala'), ('MH', 'Maharashtra'), ('MP', 'Madhya Pradesh'), ('TN', 'Tamilnadu'), ('WB', 'West Bengal')], max_length=2)),
                ('academic_year', models.CharField(help_text='e.g., AY 2025-26', max_length=20)),
                ('document', models.FileField(help_text='Upload holiday list document (PDF)', upload_to='holidays/')),
                ('title', models.CharField(blank=True, help_text='Optional: Custom title (defaults to state name)', max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Holiday List',
                'verbose_name_plural': 'Holiday Lists',
                'ordering': ['state', '-academic_year'],
            },
        ),
    ]

