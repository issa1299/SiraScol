from django.contrib import admin
from .models import Absence


@admin.register(Absence)
class AbsenceAdmin(admin.ModelAdmin):
    list_display = ['student', 'date', 'type', 'status', 'notified_parent']
    list_filter = ['type', 'status', 'date']
    search_fields = ['student__last_name', 'student__matricule']
    date_hierarchy = 'date'
