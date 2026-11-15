from django.contrib import admin
from .models import SchoolSettings, SchoolPhoto


@admin.register(SchoolSettings)
class SchoolSettingsAdmin(admin.ModelAdmin):
    list_display = ['name', 'city', 'phone', 'director_name']


@admin.register(SchoolPhoto)
class SchoolPhotoAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_primary', 'created_at')
