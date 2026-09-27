from django.contrib import admin
from .models import OTPVerification, SMSDelivery

@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ('mobile', 'status', 'created_at', 'expires_at', 'attempts')
    list_filter = ('status',)
    search_fields = ('mobile', 'request_id')

@admin.register(SMSDelivery)
class SMSDeliveryAdmin(admin.ModelAdmin):
    list_display = ('request_id', 'mobile', 'status', 'received_at')
