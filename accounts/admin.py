from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'role', 'organisation', 'is_active']
    fieldsets = UserAdmin.fieldsets + (
        ('MoMo Shield', {'fields': ('role', 'organisation', 'phone')}),
    )
