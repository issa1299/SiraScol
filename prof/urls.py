from django.urls import path

from . import views

app_name = 'prof'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('classes/', views.classes, name='classes'),
    path('classes/<int:classroom_id>/', views.class_detail, name='class_detail'),
    path('notes/', views.notes, name='notes'),
    path('saisie-notes/', views.saisie_notes, name='saisie_notes'),
    path('appel/', views.appel, name='appel'),
    path('presences/', views.presence, name='presence'),
    path('emploi-du-temps/', views.emploi_du_temps, name='timetable'),
    path('devoirs/', views.devoirs, name='devoirs'),
    path('supports/', views.supports, name='supports'),
    path('supports/<int:pk>/supprimer/', views.support_delete, name='support_delete'),
    path('bulletins/', views.bulletins, name='bulletins'),
    path('notifications/', views.notifications, name='notifications'),
    path('rendezvous/', views.rendezvous, name='rendezvous'),
    path('messagerie/', views.messagerie, name='messages'),
    path('profil/', views.profil, name='profil'),
    path('validation/', views.validation, name='validation'),
]
