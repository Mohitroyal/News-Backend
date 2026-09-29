import uuid
from django.db import models


class Token(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_id = models.UUIDField(unique=True)
    payload_hash = models.CharField(max_length=64)
    token_number = models.CharField(max_length=80, unique=True)
    inputs = models.JSONField()
    state = models.CharField(max_length=12, default='PENDING')
    qr_url = models.URLField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
