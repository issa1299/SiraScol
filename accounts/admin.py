from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Profile


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profil'


class UserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]
    list_display = ['username', 'email', 'first_name', 'last_name', 'get_role', 'is_staff']
    list_filter = ['is_staff', 'is_superuser', 'profile__role']

    def get_role(self, obj):
        return obj.profile.get_role_display() if hasattr(obj, 'profile') else '-'
    get_role.short_description = 'Rôle'


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'phone', 'is_active']
    list_filter = ['role', 'is_active']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'phone']


from .models import WebAuthnCredential


@admin.register(WebAuthnCredential)
class WebAuthnCredentialAdmin(admin.ModelAdmin):
    list_display = ('device_name', 'user', 'created_at', 'last_used_at')
    search_fields = ('user__username', 'device_name')
    readonly_fields = ('credential_id', 'public_key', 'sign_count', 'created_at', 'last_used_at')
