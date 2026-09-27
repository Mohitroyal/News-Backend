from django.urls import path
from .views import login_view, verify_otp_view, change_number_view

app_name = 'accounts'
urlpatterns = [
    path('login/', login_view, name='login'),
    path('verify-otp/', verify_otp_view, name='verify_otp'),
    path('change-number/', change_number_view, name='change_number'),
]
