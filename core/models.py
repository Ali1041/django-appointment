from django.db import models
from django.contrib.auth.models import User


class Court(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2)
    peak_hour_rate = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Booking(models.Model):
    PAYMENT_CHOICES = [
        ("CASH", "Cash"),
        ("ONLINE", "Online"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("CONFIRMED", "Confirmed"),
        ("CANCELLED", "Cancelled"),
    ]

    court = models.ForeignKey(Court, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    booking_price = models.BigIntegerField(blank=True, null=True)
    booking_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES)
    payment_status = models.BooleanField(default=False)
    payment_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    note = models.TextField(blank=True)
    advance_payment = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    advance_payment_method = models.CharField(
        max_length=10, choices=PAYMENT_CHOICES, blank=True
    )
    ai_text = models.TextField(blank=True)
    ai_text_json = models.JSONField(null=True, blank=True)
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["court", "booking_date", "start_time", "end_time"],
                name="unique_booking",
            )
        ]


    def save(self, *args, **kwargs):
        from .utils import find_and_validate_court
        if not self.court_id:
            self.court = find_and_validate_court(self)
        if self.booking_price is None:
            self.booking_price = self.court.hourly_rate
        
        if not self.payment_amount:
            self.payment_amount = self.booking_price

        super().save(*args, **kwargs)

class Blogs(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now=True)
    cover_image = models.TextField(blank=True)
    tag = models.CharField(blank=True, max_length=100)
    status = models.CharField(blank=True, max_length=100, default="pending")

    def __str__(self):
        return self.title
