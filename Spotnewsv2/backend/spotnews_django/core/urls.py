from django.urls import path
from .views import health_check, health_msg91, admin_stats, admin_auth_users
from .admin_extras import admin_generations, admin_user_role, admin_user_plan, admin_user_ban, admin_user_delete

urlpatterns = [
    path('health', health_check, name='health_check'),
    path('health/msg91', health_msg91, name='health_msg91'),
    path('v1/admin/stats', admin_stats, name='admin_stats'),
    path('v1/admin/auth-users', admin_auth_users, name='admin_auth_users'),
    path('v1/admin/generations', admin_generations, name='admin_generations'),
    path('v1/admin/users/<uuid:user_id>/role', admin_user_role, name='admin_user_role'),
    path('v1/admin/users/<uuid:user_id>/plan', admin_user_plan, name='admin_user_plan'),
    path('v1/admin/users/<uuid:user_id>/ban', admin_user_ban, name='admin_user_ban'),
    path('v1/admin/users/<uuid:user_id>', admin_user_delete, name='admin_user_delete'),
]
