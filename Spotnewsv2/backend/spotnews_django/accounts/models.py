from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLE_CHOICES = (
        ('SUPER_ADMIN', 'Super Admin'),
        ('REPORTER', 'Reporter'),
        ('USER', 'User'),
    )
    mobile = models.CharField(max_length=15, unique=True)
    company_id = models.CharField(max_length=50, blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='USER')
    name = models.CharField(max_length=255, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'mobile'
    REQUIRED_FIELDS = ['username', 'email']
