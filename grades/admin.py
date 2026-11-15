from django.contrib import admin
from .models import Period, AssessmentType, Assessment, Grade, BulletinTemplate


@admin.register(Period)
class PeriodAdmin(admin.ModelAdmin):
    list_display = ['name', 'period_type', 'academic_year', 'start_date', 'end_date', 'order', 'is_active']
    list_filter = ['period_type', 'academic_year', 'is_active']


@admin.register(AssessmentType)
class AssessmentTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'weight']
    filter_horizontal = ['cycles']


class GradeInline(admin.TabularInline):
    model = Grade
    extra = 0


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ['title', 'assessment_type', 'subject', 'classroom', 'period', 'date', 'max_score']
    list_filter = ['assessment_type', 'period', 'subject', 'classroom__level__cycle']
    inlines = [GradeInline]
    search_fields = ['title']


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ['student', 'assessment', 'score', 'is_absent']
    list_filter = ['assessment__subject', 'is_absent', 'assessment__assessment_type']
    search_fields = ['student__last_name', 'student__matricule']


@admin.register(BulletinTemplate)
class BulletinTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'layout', 'formula', 'is_default']
    list_filter = ['category', 'is_default']
