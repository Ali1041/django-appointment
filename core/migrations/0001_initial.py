# Generated by Django 5.1.4 on 2025-01-03 16:51

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CricketNet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField()),
                ('hourly_rate', models.DecimalField(decimal_places=2, max_digits=10)),
                ('peak_hour_rate', models.DecimalField(decimal_places=2, max_digits=10)),
                ('is_active', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='Booking',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('booking_date', models.DateField()),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('payment_method', models.CharField(choices=[('CASH', 'Cash'), ('ONLINE', 'Online')], max_length=10)),
                ('payment_status', models.BooleanField(default=False)),
                ('payment_amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('payment_date', models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('CONFIRMED', 'Confirmed'), ('CANCELLED', 'Cancelled')], default='PENDING', max_length=20)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('cricket_net', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.cricketnet')),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('cricket_net', 'booking_date', 'start_time', 'end_time'), name='unique_booking')],
            },
        ),
    ]
