# Generated by Django 5.1.4 on 2025-01-03 17:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='advance_payment',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='booking',
            name='advance_payment_method',
            field=models.CharField(blank=True, choices=[('CASH', 'Cash'), ('ONLINE', 'Online')], max_length=10),
        ),
        migrations.AddField(
            model_name='booking',
            name='note',
            field=models.TextField(blank=True),
        ),
    ]