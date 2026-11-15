from django.contrib import admin
from .models import Student, Parent, ParentStudent, Enrollment


class ParentStudentInline(admin.TabularInline):
    model = ParentStudent
    extra = 1


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0
    readonly_fields = ['created_at']


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['matricule', 'last_name', 'first_name', 'gender', 'status', 'enrollment_date']
    list_filter = ['status', 'gender']
    search_fields = ['matricule', 'first_name', 'last_name']
    inlines = [ParentStudentInline, EnrollmentInline]
    date_hierarchy = 'enrollment_date'
    readonly_fields = ['matricule']  # Généré automatiquement à la sauvegarde


@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    list_display = ['last_name', 'first_name', 'phone', 'email']
    search_fields = ['last_name', 'first_name', 'phone']


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ['student', 'classroom', 'academic_year', 'is_active', 'enrollment_date']
    list_filter = ['academic_year', 'is_active', 'classroom']
    search_fields = ['student__matricule', 'student__last_name']
