from django.db import models
from django.utils.timezone import now
from datetime import timedelta

class OTPVerification(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('VERIFIED', 'Verified'),
        ('EXPIRED', 'Expired'),
        ('FAILED', 'Failed'),
    )
    mobile = models.CharField(max_length=15)
    otp_hash = models.CharField(max_length=128)
    request_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(blank=True, null=True)
    attempts = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = now() + timedelta(minutes=5)
        super().save(*args, **kwargs)

class SMSDelivery(models.Model):
    STATUS_CHOICES = (
        ('ACCEPTED', 'Accepted'),
        ('DELIVERED', 'Delivered'),
        ('FAILED', 'Failed'),
        ('UNKNOWN', 'Unknown'),
    )
    request_id = models.CharField(max_length=100)
    mobile = models.CharField(max_length=15)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UNKNOWN')
    provider_response = models.JSONField(blank=True, null=True)
    received_at = models.DateTimeField(auto_now_add=True)
