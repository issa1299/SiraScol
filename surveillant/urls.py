from django.urls import path

from . import views

app_name = 'surveillant'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('pointage/', views.pointage, name='pointage'),
    path('presences/', views.presences, name='presences'),
    path('presences/<int:pk>/modifier/', views.presence_edit, name='presence_edit'),
    path('absences/', views.absences, name='absences'),
    path('absences/ajouter/', views.absence_create, name='absence_create'),
    path('absences/<int:pk>/justifier/', views.absence_justify, name='absence_justify'),
    path('retards/', views.retards, name='retards'),
    path('discipline/', views.discipline, name='discipline'),
    path('discipline/ajouter/', views.discipline_create, name='discipline_create'),
    path('discipline/<int:pk>/commentaire/', views.discipline_comment, name='discipline_comment'),
    path('sorties/', views.sorties, name='sorties'),
    path('sorties/ajouter/', views.sortie_create, name='sortie_create'),
    path('sorties/<int:pk>/retour/', views.sortie_return, name='sortie_return'),
    path('historique/', views.historique, name='historique'),
    path('rapports/', views.rapports, name='rapports'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/direction/', views.notify_direction, name='notify_direction'),
    path('profil/', views.profil, name='profil'),
]
