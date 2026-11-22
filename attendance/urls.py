from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    path('', views.attendance_classes, name='list'),
    path('pdf/', views.absence_list_pdf, name='list_pdf'),
    path('classes/', views.attendance_classes, name='classes'),
    path('classes/<int:classroom_id>/', views.class_attendance, name='class_attendance'),
    path('historique/', views.absence_list, name='history'),
    path('historique/pdf/', views.absence_list_pdf, name='history_pdf'),
    path('ajouter/', views.absence_create, name='create'),
    path('scan/', views.scan_qr, name='scan'),
    path('scan/api/', views.scan_qr_api, name='scan_api'),
    path('scan/pointe/<int:pk>/', views.scan_punch_detail, name='scan_punch_detail'),
    path('scan/saisie/', views.scan_manual, name='scan_manual'),
    path('scan/aide/', views.scan_camera_help, name='scan_camera_help'),
]
