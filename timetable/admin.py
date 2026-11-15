from django.contrib import admin
from .models import Room, TimeSlot, TimetableEntry


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ['name', 'capacity', 'building']


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_time', 'end_time', 'order']
    ordering = ['order']


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ['classroom', 'day', 'time_slot', 'subject', 'teacher', 'room']
    list_filter = ['day', 'classroom', 'subject']
