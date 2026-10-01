from django.urls import path
from .views import dashboard_view, profile_view, settings_view

app_name = 'dashboard'
urlpatterns = [
    path('', dashboard_view, name='dashboard'),
    path('profile/', profile_view, name='profile'),
    path('settings/', settings_view, name='settings'),
]
