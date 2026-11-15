from django.contrib import admin
from .models import AcademicYear, Cycle, Level, ClassRoom, Subject, SubjectAssignment, ClassSubject


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'is_current']
    list_filter = ['is_current']


@admin.register(Cycle)
class CycleAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'order']
    ordering = ['order']


@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ['name', 'cycle', 'order']
    list_filter = ['cycle']
    ordering = ['cycle__order', 'order']


@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'level', 'get_cycle', 'serie', 'academic_year', 'capacity', 'main_teacher', 'student_count']
    list_filter = ['academic_year', 'level__cycle', 'level']
    search_fields = ['name']

    @admin.display(description='Cycle')
    def get_cycle(self, obj):
        return obj.level.cycle.name


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'coefficient', 'is_active']
    list_filter = ['is_active', 'cycles']
    search_fields = ['name', 'code']
    filter_horizontal = ['cycles']


@admin.register(SubjectAssignment)
class SubjectAssignmentAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'subject', 'classroom', 'hours_per_week']
    list_filter = ['classroom__academic_year', 'classroom__level__cycle', 'subject']


@admin.register(ClassSubject)
class ClassSubjectAdmin(admin.ModelAdmin):
    list_display = ('classroom', 'subject', 'coefficient', 'hours_per_week', 'order')
    list_filter = ('classroom__academic_year', 'classroom__level')
    search_fields = ('subject__name', 'classroom__name')
