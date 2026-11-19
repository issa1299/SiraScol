from django.urls import path

from . import views

app_name = 'parent'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('enfants/', views.enfants, name='enfants'),
    path('notes/', views.notes, name='notes'),
    path('bulletins/', views.bulletins, name='bulletins'),
    path('absences/', views.absences, name='absences'),
    path('paiements/', views.paiements, name='paiements'),
    path('emploi-du-temps/', views.emploi_du_temps, name='timetable'),
    path('devoirs/', views.devoirs, name='devoirs'),
    path('communication/', views.communication, name='communication'),
    path('notifications/', views.notifications, name='notifications'),
    path('profil/', views.profil, name='profil'),
]
