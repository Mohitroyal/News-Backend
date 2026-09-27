from django.urls import path
from .views import send_otp_api, verify_otp_api, resend_otp_api, logout_api, me_api, msg91_webhook

urlpatterns = [
    path('send-otp', send_otp_api, name='send_otp_api'),
    path('verify-otp', verify_otp_api, name='verify_otp_api'),
    path('resend-otp', resend_otp_api, name='resend_otp_api'),
    path('logout', logout_api, name='logout_api'),
    path('me', me_api, name='me_api'),
    path('../webhooks/msg91/', msg91_webhook, name='msg91_webhook'),
]
