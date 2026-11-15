from django.contrib import admin
from .models import Teacher, StaffContract, StaffAttendance, StaffSalary, StaffDocument

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('matricule', 'last_name', 'first_name', 'category', 'status', 'speciality')
    list_filter = ('category', 'status')
    search_fields = ('matricule', 'last_name', 'first_name')

admin.site.register(StaffContract)
admin.site.register(StaffAttendance)
admin.site.register(StaffSalary)
admin.site.register(StaffDocument)
