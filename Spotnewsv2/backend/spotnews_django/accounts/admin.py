from django.contrib import admin
from .models import User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('mobile', 'name', 'role', 'is_active')
    list_filter = ('role', 'is_active')
    search_fields = ('mobile', 'name', 'email')
