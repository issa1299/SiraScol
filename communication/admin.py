from django.contrib import admin
from .models import SchoolDocument, Announcement, Message


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ['title', 'target', 'author', 'is_published', 'published_at']
    list_filter = ['target', 'is_published']
    search_fields = ['title', 'content']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['subject', 'sender', 'recipient', 'is_read', 'sent_at']
    list_filter = ['is_read']
    search_fields = ['subject', 'body']


@admin.register(SchoolDocument)
class SchoolDocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'is_published', 'created_at']
    list_filter = ['category', 'is_published']
